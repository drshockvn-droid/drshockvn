import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import db, tools

p = os.path.join(tempfile.mkdtemp(), "t.db")
db.init(p)
with db.connect(p) as c:
    db.upsert_part(c, "PH-VIOS-R", "Phuộc sau KYB Vios", "Phuộc", "Toyota Vios 2014-2018", 4, 1450000, "A2")
    db.upsert_part(c, "PH-VIOS-F", "Phuộc trước KYB Vios", "Phuộc", "Toyota Vios 2014-2018", 0, 1650000, "A1")

r = tools.run("search_inventory", {"query": "phuoc", "vehicle": "vios 2016"}, {}, p)
assert r["exact_match"] and len(r["results"]) == 2, r
assert tools.run("search_inventory", {"query": "phuộc", "in_stock_only": True}, {}, p)["results"][0]["sku"] == "PH-VIOS-R"

b = tools.run("record_bill", {"plate": "51k-123.45", "items": [
    {"kind": "part", "name": "Phuộc sau", "qty": 2, "unit_price": 1450000, "sku": "PH-VIOS-R"},
    {"kind": "labor", "name": "Công thay", "unit_price": 300000}]}, {"user": "Tuấn"}, p)
assert b["total_vnd"] == 3200000 and b["plate"] == "51K12345", b
stock = lambda: tools.run("search_inventory", {"query": "phuoc sau"}, {}, p)["results"][0]["qty"]
assert stock() == 2
assert tools.run("vehicle_history", {"plate": "51K-123.45"}, {}, p)["visits"][0]["total"] == 3200000
assert tools.run("void_bill", {"bill_id": b["bill_id"]}, {}, p) == {"voided": b["bill_id"]}
assert stock() == 4
assert "error" in tools.run("record_bill", {"plate": "x", "items": []}, {}, p)
print("OK")
assert tools.run("search_inventory", {"query": "phuoc", "vehicle": "Vios 2022"}, {}, p)["exact_match"] is False
