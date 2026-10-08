import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import tools
from store import MemoryStore

s = MemoryStore([
    {"id": "P01", "name": "Phuộc sau KYB Vios 2014-2018", "cat": "PHUOC", "unit": "Cái", "costPrice": 900000, "price": 1450000, "stock": 4},
    {"id": "P02", "name": "Phuộc trước KYB Vios 2014-2018", "cat": "PHUOC", "unit": "Cái", "costPrice": 1000000, "price": 1650000, "stock": 0},
    {"id": "P03", "name": "Nhớt Castrol 5W30", "cat": "NHOT", "unit": "Lít", "price": 195000, "stock": 12},
])
run = lambda n, a, c=None: tools.run(n, a, c or {"user": "Tuấn"}, s)

r = run("search_inventory", {"query": "phuoc", "vehicle": "Vios 2016"})
assert r["exact_match"] and [p["id"] for p in r["results"]] == ["P01", "P02"], r  # còn hàng xếp trước
assert all("costPrice" not in p for p in r["results"])  # không lộ giá vốn
assert run("search_inventory", {"query": "phuoc", "vehicle": "Vios 2022"})["exact_match"] is False
assert [p["id"] for p in run("search_inventory", {"query": "phuoc", "in_stock_only": True})["results"]] == ["P01"]

b = run("record_bill", {"plate": "51k-123.45", "car": "Vios 2016", "items": [
    {"name": "Phuộc sau KYB Vios 2014-2018", "id": "P01", "qty": 2},
    {"name": "Công thay phuộc", "unit_price": 300000}]})
assert b["total_vnd"] == 3200000 and b["bill_id"] == "INV-101" and b["plate"] == "51K-123.45", b
stock = lambda: next(p["stock"] for p in s.inventory() if p["id"] == "P01")
assert stock() == 2 and s._logs[0]["type"] == "XUAT"
inv = s.invoices()[0]
assert inv["name"] == "Khách lẻ" and inv["subtotal"] == 3200000 and inv["items"][0]["price"] == 1450000
assert run("vehicle_history", {"plate": "51K12345"})["visits"][0]["total"] == 3200000
assert run("today_summary", {})["count"] == 1
assert "error" in run("record_bill", {"plate": "51K-123.45", "car": "x", "items": [{"name": "Z", "id": "NOPE"}]})
assert "error" in run("record_bill", {"plate": "x", "car": "x", "items": []})
assert run("void_bill", {"bill_id": "inv-101"}) == {"voided": "INV-101"}
assert stock() == 4 and not s.invoices()
assert "error" in run("void_bill", {"bill_id": "INV-101"})
print("OK")
