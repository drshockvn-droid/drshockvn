"""Các tool Claude được phép gọi. Mọi tính toán tiền/tồn kho làm ở đây, không để AI tự tính."""
import re

import db

TOOLS = [
    {
        "name": "record_bill",
        "description": "Ghi nhận phiếu/bill của 1 xe vào database. Chỉ gọi khi đã đọc được biển số và ít nhất 1 hạng mục. "
                       "Tổng tiền do hệ thống tự tính. Nếu hạng mục là phụ tùng có trong kho, truyền sku để trừ tồn.",
        "input_schema": {
            "type": "object",
            "properties": {
                "plate": {"type": "string", "description": "Biển số xe, vd 51K-123.45"},
                "vehicle": {"type": "string", "description": "Hãng/dòng/đời xe nếu biết"},
                "customer": {"type": "string"},
                "note": {"type": "string"},
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "kind": {"type": "string", "enum": ["labor", "part"]},
                            "name": {"type": "string"},
                            "qty": {"type": "integer", "minimum": 1},
                            "unit_price": {"type": "integer", "description": "VND, số nguyên"},
                            "sku": {"type": "string"},
                        },
                        "required": ["name", "unit_price"],
                    },
                },
            },
            "required": ["plate", "items"],
        },
    },
    {
        "name": "search_inventory",
        "description": "Tra kho hàng thực tế của Dr.ShockVN (tồn kho, giá, vị trí). Luôn dùng tool này trước khi nói còn/hết hàng.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Tên/loại hàng, vd 'phuộc sau', 'nhớt 5W30'"},
                "vehicle": {"type": "string", "description": "Hãng/dòng/đời xe để lọc hàng tương thích, vd 'Vios 2016'"},
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
        "description": "Huỷ 1 bill đã ghi nhầm và hoàn lại tồn kho.",
        "input_schema": {"type": "object", "properties": {"bill_id": {"type": "integer"}}, "required": ["bill_id"]},
    },
    {
        "name": "today_summary",
        "description": "Tổng hợp các bill trong ngày hôm nay.",
        "input_schema": {"type": "object", "properties": {}},
    },
]


def run(name: str, args: dict, ctx: dict, path: str) -> dict:
    with db.connect(path) as c:
        return globals()[f"_{name}"](c, args, ctx)


def _record_bill(c, a, ctx):
    plate = db.norm_plate(a.get("plate", ""))
    items = a.get("items") or []
    if len(plate) < 5 or not items:
        return {"error": "thiếu biển số hợp lệ hoặc hạng mục"}
    warnings, rows, total = [], [], 0
    for it in items:
        qty = max(int(it.get("qty") or 1), 1)
        price = max(int(it.get("unit_price") or 0), 0)
        kind = it.get("kind") or "labor"
        sku = (it.get("sku") or "").strip()
        if sku and kind == "part":
            p = c.execute("SELECT qty FROM inventory WHERE sku=?", (sku,)).fetchone()
            if not p:
                warnings.append(f"SKU {sku} không có trong kho, không trừ tồn")
                sku = ""
            elif p["qty"] < qty:
                warnings.append(f"SKU {sku} chỉ còn {p['qty']} < {qty}, đã trừ về 0 — cần kiểm kho")
        rows.append((kind, it["name"], sku, qty, price))
        total += qty * price
    cur = c.execute(
        "INSERT INTO bills(plate,vehicle,customer,note,total,created_by,chat_id,photo_file_id) VALUES(?,?,?,?,?,?,?,?)",
        (plate, a.get("vehicle", ""), a.get("customer", ""), a.get("note", ""), total,
         ctx.get("user", ""), ctx.get("chat_id"), ctx.get("photo_file_id", "")),
    )
    bid = cur.lastrowid
    for kind, name, sku, qty, price in rows:
        c.execute("INSERT INTO bill_items(bill_id,kind,name,sku,qty,unit_price) VALUES(?,?,?,?,?,?)",
                  (bid, kind, name, sku, qty, price))
        if sku:
            c.execute("UPDATE inventory SET qty=MAX(qty-?,0) WHERE sku=?", (qty, sku))
    return {"bill_id": bid, "plate": plate, "total_vnd": total, "items": len(rows), "warnings": warnings}


def _year_ok(compat: str, year: int) -> bool:
    """compat có khoảng năm (2014-2018 / 2016) thì năm xe phải nằm trong; không ghi năm thì coi là phù hợp."""
    spans = re.findall(r"(\d{4})(?:\s*-\s*(\d{4}))?", compat)
    if not spans:
        return True
    return any(int(a) <= year <= int(b or a) for a, b in spans)


def _search_inventory(c, a, ctx):
    q_words = db.norm(a["query"]).split()
    v_words = db.norm(a.get("vehicle", "")).split()
    year = next((int(w) for w in v_words if re.fullmatch(r"(19|20)\d{2}", w)), None)
    v_words = [w for w in v_words if not re.fullmatch(r"(19|20)\d{2}", w)]

    def fetch(words):
        sql = "SELECT sku,name,category,compat,qty,price,location FROM inventory WHERE 1=1"
        sql += "".join(" AND search_text LIKE ?" for _ in words)
        if a.get("in_stock_only"):
            sql += " AND qty>0"
        return [dict(r) for r in c.execute(sql + " ORDER BY qty>0 DESC, name LIMIT 30", [f"%{w}%" for w in words])]

    rows = fetch(q_words + v_words)
    if year:
        rows = [r for r in rows if _year_ok(r["compat"], year)]
    rows = rows[:15]
    if not rows and v_words:
        # nới lỏng: bỏ điều kiện xe, AI phải nói rõ chưa xác nhận tương thích
        return {"exact_match": False, "results": fetch(q_words)[:10],
                "note": "không có hàng ghi tương thích với xe này; đây là hàng cùng loại, CHƯA xác nhận tương thích"}
    return {"exact_match": True, "results": rows}


def _vehicle_history(c, a, ctx):
    plate = db.norm_plate(a["plate"])
    out = []
    for b in c.execute("SELECT * FROM bills WHERE plate=? AND status='open' ORDER BY id DESC LIMIT 10", (plate,)):
        items = [dict(i) for i in c.execute(
            "SELECT kind,name,qty,unit_price FROM bill_items WHERE bill_id=?", (b["id"],))]
        out.append({"bill_id": b["id"], "date": b["created_at"], "vehicle": b["vehicle"],
                    "total": b["total"], "items": items})
    return {"plate": plate, "visits": out}


def _void_bill(c, a, ctx):
    b = c.execute("SELECT status FROM bills WHERE id=?", (a["bill_id"],)).fetchone()
    if not b:
        return {"error": "không có bill này"}
    if b["status"] == "void":
        return {"error": "bill đã huỷ trước đó"}
    for i in c.execute("SELECT sku,qty FROM bill_items WHERE bill_id=? AND sku!=''", (a["bill_id"],)).fetchall():
        c.execute("UPDATE inventory SET qty=qty+? WHERE sku=?", (i["qty"], i["sku"]))
    c.execute("UPDATE bills SET status='void' WHERE id=?", (a["bill_id"],))
    return {"voided": a["bill_id"]}


def _today_summary(c, a, ctx):
    rows = [dict(r) for r in c.execute(
        "SELECT id,plate,vehicle,total,created_by FROM bills WHERE status='open' AND date(created_at)=date('now','localtime') ORDER BY id")]
    return {"count": len(rows), "revenue_vnd": sum(r["total"] for r in rows), "bills": rows}
