"""Lớp truy cập dữ liệu. Production = Firebase Realtime DB của webapp (garage/inventory, garage/invoices,
garage/stockLogs) theo ĐÚNG định dạng index.html đang dùng, để bill bot ghi hiện ngay trong webapp.
MemoryStore dùng cho test."""
import copy
import os
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def _now():
    return datetime.now(TZ)


def fmt_date(d):  # giống toLocaleDateString('vi-VN') + HH:mm của webapp: 8/10/2026 14:30
    return f"{d.day}/{d.month}/{d.year} {d:%H:%M}"


def fmt_time(d):
    return f"{d.day}/{d.month}/{d.year} {d:%H:%M:%S}"


def to_list(v):
    if not v:
        return []
    if isinstance(v, list):
        return [x for x in v if x is not None]
    if isinstance(v, dict):
        return [v[k] for k in sorted(v, key=lambda k: (not str(k).isdigit(), int(k) if str(k).isdigit() else 0))]
    return []


def num(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def public_item(p):
    """Bỏ ảnh base64 và giá vốn — bot không được lộ giá vốn."""
    return {"id": p.get("id"), "name": p.get("name"), "cat": p.get("cat"), "unit": p.get("unit", "Cái"),
            "price": p.get("price", 0), "stock": num(p.get("stock"))}


def make_invoice_entry(inv, new_id):
    inv = copy.deepcopy(inv)
    inv["id"] = new_id
    inv["date"] = fmt_date(_now())
    return inv


def next_invoice_id(invoices):
    nums = [int(i["id"][4:]) for i in invoices if str(i.get("id", "")).startswith("INV-") and i["id"][4:].isdigit()]
    return f"INV-{max(nums, default=100) + 1}"


def stock_log(type_, item, before, after, user, note):
    return {"id": "LOG-" + str(int(time.time() * 1000))[-6:], "time": fmt_time(_now()), "type": type_,
            "itemId": item.get("id", "---"), "itemName": item.get("name", "Phụ tùng"), "unit": item.get("unit", "Cái"),
            "beforeQty": before, "afterQty": after, "diff": round(after - before, 1), "user": user, "note": note}


class MemoryStore:
    def __init__(self, inventory=None, invoices=None):
        self._inv, self._bills, self._logs = list(inventory or []), list(invoices or []), []

    def inventory(self):
        return [public_item(p) for p in self._inv]

    def adjust_stock(self, item_id, delta, type_, user, note):
        p = next((p for p in self._inv if p["id"] == item_id), None)
        if not p:
            return None
        before = num(p.get("stock"))
        after = max(0, round(before + delta, 1))
        p["stock"] = after
        self._logs.insert(0, stock_log(type_, p, before, after, user, note))
        return before, after

    def add_invoice(self, inv):
        e = make_invoice_entry(inv, next_invoice_id(self._bills))
        self._bills.insert(0, e)
        return e

    def invoices(self):
        return copy.deepcopy(self._bills)

    def delete_invoice(self, inv_id):
        e = next((i for i in self._bills if i["id"] == inv_id), None)
        if e:
            self._bills.remove(e)
        return e


class FirebaseStore:
    """Cần service account (Firebase Console → Project settings → Service accounts → Generate key).
    Admin SDK bỏ qua security rules nên KHÔNG cần mở rules công khai."""

    def __init__(self, cred_path, db_url):
        import firebase_admin
        from firebase_admin import credentials, db

        firebase_admin.initialize_app(credentials.Certificate(cred_path), {"databaseURL": db_url})
        self.db = db
        self._cache, self._cache_t, self._lock = [], 0.0, threading.Lock()

    def _ref(self, p):
        return self.db.reference(p)

    def _raw_inventory(self):
        with self._lock:
            if time.time() - self._cache_t > 20:
                self._cache, self._cache_t = to_list(self._ref("garage/inventory").get()), time.time()
            return self._cache

    def inventory(self):
        return [public_item(p) for p in self._raw_inventory()]

    def _push_log(self, entry):
        def fn(cur):
            return [entry] + to_list(cur)
        self._ref("garage/stockLogs").transaction(fn)

    def adjust_stock(self, item_id, delta, type_, user, note):
        for attempt in range(2):
            raw = self._raw_inventory()
            idx = next((i for i, p in enumerate(raw) if p.get("id") == item_id), None)
            if idx is None:
                return None
            res = {}

            def fn(cur):
                # index có thể lệch nếu webapp vừa thêm/xoá mã hàng → chỉ sửa khi đúng id, ngược lại giữ nguyên
                if not cur or cur.get("id") != item_id:
                    res["miss"] = True
                    return cur
                before = num(cur.get("stock"))
                after = max(0, round(before + delta, 1))
                cur["stock"] = after
                res.update(before=before, after=after, item=dict(cur), miss=False)
                return cur

            self._ref(f"garage/inventory/{idx}").transaction(fn)
            if not res.get("miss"):
                self._cache_t = 0
                self._push_log(stock_log(type_, res["item"], res["before"], res["after"], user, note))
                return res["before"], res["after"]
            self._cache_t = 0  # làm mới cache rồi thử lại
        return None

    def add_invoice(self, inv):
        res = {}

        def fn(cur):
            lst = to_list(cur)
            res["e"] = make_invoice_entry(inv, next_invoice_id(lst))
            return [res["e"]] + lst  # webapp dùng unshift: bill mới nằm đầu mảng

        self._ref("garage/invoices").transaction(fn)
        return res["e"]

    def invoices(self):
        return to_list(self._ref("garage/invoices").get())

    def delete_invoice(self, inv_id):
        res = {}

        def fn(cur):
            lst = to_list(cur)
            res["e"] = next((i for i in lst if i.get("id") == inv_id), None)
            return [i for i in lst if i.get("id") != inv_id] if res["e"] else cur

        self._ref("garage/invoices").transaction(fn)
        return res["e"]


def from_env():
    return FirebaseStore(os.environ["FIREBASE_CREDENTIALS"], os.environ["FIREBASE_DB_URL"])
