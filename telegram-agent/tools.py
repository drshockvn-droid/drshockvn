"""Các tool Claude được phép gọi. Tính tiền/tồn kho làm ở đây, không để AI tự tính."""
import re

import db_text
from store import num

TOOLS = [
    {
        "name": "record_bill",
        "description": "Ghi bill 1 xe vào hệ thống webapp (hiện ngay trong tab hoá đơn) và tự trừ tồn kho phụ tùng. "
                       "Chỉ gọi khi đã đọc được biển số, dòng xe và ít nhất 1 hạng mục. Tổng tiền hệ thống tự tính. "
                       "Phụ tùng lấy từ kho PHẢI truyền id đúng của mã hàng (lấy từ search_inventory); công/dịch vụ thì bỏ id.",
        "input_schema": {
            "type": "object",
            "properties": {
                "plate": {"type": "string", "description": "Biển số xe, vd 51K-123.45"},
                "car": {"type": "string", "description": "Dòng xe/đời xe, vd 'Vios 2016'"},
                "customer": {"type": "string", "description": "Tên khách; không biết thì bỏ trống"},
                "phone": {"type": "string"},
                "odo": {"type": "string"},
                "note": {"type": "string"},
                "discount": {"type": "integer", "description": "Giảm giá VND, mặc định 0"},
                "service_type": {"type": "string", "enum": ["Lắp tại xưởng", "Gửi về"]},
                "customer_type": {"type": "string", "enum": ["Khách lẻ", "Khách Garage / Đại lý"]},
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "id": {"type": "string", "description": "id mã hàng trong kho (chỉ với phụ tùng)"},
                            "qty": {"type": "number"},
                            "unit_price": {"type": "integer", "description": "VND/đơn vị. Bỏ trống với phụ tùng để dùng giá niêm yết"},
                            "unit": {"type": "string"},
                        },
                        "required": ["name"],
                    },
                },
            },
            "required": ["plate", "car", "items"],
        },
    },
    {
        "name": "search_inventory",
        "description": "Tra kho hàng thực tế của Dr.ShockVN (tồn kho, giá bán). Luôn dùng tool này trước khi nói còn/hết hàng.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Tên/loại hàng, vd 'phuộc sau', 'nhớt 5W30'"},
                "vehicle": {"type": "string", "description": "Dòng/đời xe để lọc hàng hợp xe, vd 'Vios 2016'"},
                "in_stock_only": {"type": "boolean"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "vehicle_history",
        "description": "Lịch sử các lần vào xưởng của 1 biển số (để đề xuất hạng mục dựa trên lần trước).",
        "input_schema": {"type": "object", "properties": {"plate": {"type": "string"}}, "required": ["plate"]},
    },
    {
        "name": "void_bill",
        "description": "Xoá 1 bill ghi nhầm (vd INV-105) và hoàn lại tồn kho.",
        "input_schema": {"type": "object", "properties": {"bill_id": {"type": "string"}}, "required": ["bill_id"]},
    },
    {
        "name": "today_summary",
        "description": "Tổng hợp các bill trong ngày hôm nay.",
        "input_schema": {"type": "object", "properties": {}},
    },
]


def norm_plate(p):
    return "".join(c for c in (p or "").upper() if c.isalnum())


def run(name, args, ctx, store):
    return globals()[f"_{name}"](store, args, ctx)


def _record_bill(s, a, ctx):
    plate = (a.get("plate") or "").strip().upper()
    if len(norm_plate(plate)) < 5 or not a.get("items") or not (a.get("car") or "").strip():
        return {"error": "thiếu biển số hợp lệ, dòng xe hoặc hạng mục"}
    stock = {p["id"]: p for p in s.inventory()}
    items, warnings, deduct = [], [], []
    for it in a["items"]:
        qty = num(it.get("qty"), 1) or 1
        pid = (it.get("id") or "").strip()
        p = stock.get(pid) if pid else None
        if pid and not p:
            return {"error": f"id '{pid}' không có trong kho — hãy search_inventory để lấy đúng id"}
        price = it.get("unit_price")
        if price is None:
            if not p:
                return {"error": f"hạng mục '{it['name']}' thiếu đơn giá"}
            price = p["price"]
        if p:
            if p["stock"] < qty:
                warnings.append(f"{p['name']}: tồn {p['stock']:g} < cần {qty:g} — cần kiểm kho")
            deduct.append((p, qty))
        items.append({"id": pid or f"LBR_{len(items)+1}_{abs(hash(it['name'])) % 10**6}", "name": it["name"],
                      "unit": it.get("unit") or (p["unit"] if p else "Lần"), "qty": qty, "price": int(price)})
    subtotal = sum(i["qty"] * i["price"] for i in items)
    discount = max(int(a.get("discount") or 0), 0)
    inv = s.add_invoice({
        "plate": plate, "name": (a.get("customer") or "").strip() or "Khách lẻ", "phone": a.get("phone", ""),
        "car": a["car"], "odo": a.get("odo", ""), "note": (a.get("note", "") + f" [Bot Telegram - {ctx.get('user','')}]").strip(),
        "serviceType": a.get("service_type", "Lắp tại xưởng"), "customerType": a.get("customer_type", "Khách lẻ"),
        "advisor": ctx.get("user", "Bot Telegram"), "items": items,
        "subtotal": subtotal, "discount": discount, "total": max(0, subtotal - discount)})
    for p, qty in deduct:
        s.adjust_stock(p["id"], -qty, "XUAT", ctx.get("user", "Bot Telegram"),
                       f"Xuất theo hóa đơn {inv['id']} cho xe {plate} (Bot Telegram)")
    return {"bill_id": inv["id"], "plate": plate, "total_vnd": inv["total"], "items": len(items), "warnings": warnings}


def _year_ok(text, year):
    spans = re.findall(r"((?:19|20)\d{2})(?:\s*-\s*((?:19|20)\d{2}))?", text)
    return not spans or any(int(a) <= year <= int(b or a) for a, b in spans)


def _search_inventory(s, a, ctx):
    q = db_text.norm(a["query"]).split()
    v = db_text.norm(a.get("vehicle", "")).split()
    year = next((int(w) for w in v if re.fullmatch(r"(19|20)\d{2}", w)), None)
    v = [w for w in v if not re.fullmatch(r"(19|20)\d{2}", w)]
    inv = s.inventory()

    def match(words, only_stock=a.get("in_stock_only")):
        out = []
        for p in inv:
            hay = db_text.norm(f"{p['id']} {p['name']} {p['cat']}")
            if all(w in hay for w in words) and (not only_stock or p["stock"] > 0):
                out.append(p)
        return out

    rows = match(q + v)
    if year:
        rows = [p for p in rows if _year_ok(p["name"], year)]
    rows.sort(key=lambda p: (p["stock"] <= 0, p["name"]))
    if not rows and v:
        return {"exact_match": False, "results": sorted(match(q), key=lambda p: (p["stock"] <= 0, p["name"]))[:10],
                "note": "không có mã hàng ghi hợp với xe này; đây là hàng cùng loại, CHƯA xác nhận lắp vừa — thợ phải kiểm tra"}
    return {"exact_match": True, "results": rows[:15],
            "note": "kho không có cột tương thích xe: tương thích chỉ suy từ tên mã hàng, thợ vẫn nên đối chiếu"}


def _vehicle_history(s, a, ctx):
    plate = norm_plate(a["plate"])
    visits = [{"bill_id": i["id"], "date": i.get("date"), "car": i.get("car"), "odo": i.get("odo"),
               "total": i.get("total"), "items": [{"name": x["name"], "qty": x["qty"], "price": x["price"]}
                                                    for x in i.get("items", [])]}
              for i in s.invoices() if norm_plate(i.get("plate")) == plate]
    return {"plate": plate, "visits": visits[:10]}


def _void_bill(s, a, ctx):
    inv = s.delete_invoice(str(a["bill_id"]).strip().upper())
    if not inv:
        return {"error": "không có bill này"}
    for it in inv.get("items", []):
        s.adjust_stock(it["id"], num(it.get("qty"), 1), "NHAP", ctx.get("user", "Bot Telegram"),
                       f"Hoàn kho do xoá hóa đơn {inv['id']} (Bot Telegram)")
    return {"voided": inv["id"]}


def _today_summary(s, a, ctx):
    today = db_text.today_prefix()
    rows = [{"id": i["id"], "plate": i.get("plate"), "car": i.get("car"), "total": i.get("total", 0)}
            for i in s.invoices() if str(i.get("date", "")).startswith(today + " ")]
    return {"count": len(rows), "revenue_vnd": sum(r["total"] for r in rows), "bills": rows}
