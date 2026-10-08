import unicodedata

from store import _now


def norm(s):
    """Bỏ dấu, hạ chữ thường: 'Nhớt Đầu' -> 'nhot dau'."""
    s = unicodedata.normalize("NFD", s or "").replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in s if unicodedata.category(c) != "Mn").lower()


def today_prefix():
    d = _now()
    return f"{d.day}/{d.month}/{d.year}"
