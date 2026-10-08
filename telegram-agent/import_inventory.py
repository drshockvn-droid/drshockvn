"""Nạp kho hàng từ CSV (xuất từ Excel/Google Sheet). Chạy lại bất cứ lúc nào để đồng bộ.
Cột: sku,name,category,compat,qty,price,location
Dùng: python import_inventory.py kho.csv
"""
import csv
import os
import sys

import db

path = os.getenv("DB_PATH", "garage.db")
db.init(path)
with db.connect(path) as c, open(sys.argv[1], encoding="utf-8-sig") as f:
    n = 0
    for r in csv.DictReader(f):
        db.upsert_part(c, r["sku"].strip(), r["name"].strip(), r.get("category", ""), r.get("compat", ""),
                       int(r.get("qty") or 0), int(r.get("price") or 0), r.get("location", ""))
        n += 1
print(f"Đã nạp {n} mặt hàng")
