"""SQLite: hoá đơn (bills) + kho hàng (inventory)."""
import sqlite3
import unicodedata
from contextlib import contextmanager

SCHEMA = """
CREATE TABLE IF NOT EXISTS inventory (
  sku TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  category TEXT DEFAULT '',
  compat TEXT DEFAULT '',          -- hãng/dòng xe/đời xe tương thích, vd: "Toyota Vios 2014-2018; Honda City"
  qty INTEGER NOT NULL DEFAULT 0,
  price INTEGER NOT NULL DEFAULT 0, -- giá bán (VND)
  location TEXT DEFAULT '',
  search_text TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS bills (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  plate TEXT NOT NULL,
  vehicle TEXT DEFAULT '',
  customer TEXT DEFAULT '',
  note TEXT DEFAULT '',
  total INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'open',   -- open | void
  created_by TEXT DEFAULT '',
  chat_id INTEGER,
  photo_file_id TEXT DEFAULT '',
  created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS bill_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  bill_id INTEGER NOT NULL REFERENCES bills(id),
  kind TEXT NOT NULL DEFAULT 'labor',    -- labor (công) | part (phụ tùng)
  name TEXT NOT NULL,
  sku TEXT DEFAULT '',
  qty INTEGER NOT NULL DEFAULT 1,
  unit_price INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_bills_plate ON bills(plate);
"""


def norm(s: str) -> str:
    """Bỏ dấu, hạ chữ thường: 'Nhớt Đầu' -> 'nhot dau'."""
    s = unicodedata.normalize("NFD", s or "").replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in s if unicodedata.category(c) != "Mn").lower()


def norm_plate(p: str) -> str:
    return "".join(c for c in (p or "").upper() if c.isalnum())


@contextmanager
def connect(path: str):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init(path: str):
    with connect(path) as c:
        c.executescript(SCHEMA)


def upsert_part(c, sku, name, category="", compat="", qty=0, price=0, location=""):
    st = norm(" ".join([sku, name, category, compat]))
    c.execute(
        """INSERT INTO inventory(sku,name,category,compat,qty,price,location,search_text)
           VALUES(?,?,?,?,?,?,?,?)
           ON CONFLICT(sku) DO UPDATE SET name=excluded.name, category=excluded.category,
             compat=excluded.compat, qty=excluded.qty, price=excluded.price,
             location=excluded.location, search_text=excluded.search_text""",
        (sku, name, category, compat, qty, price, location, st),
    )
