# Dr.ShockVN — AI trưởng nhóm Telegram

Bot trong group nội bộ garage:
1. **Ghi bill**: nhân viên gửi ảnh xe + chú thích (biển số, việc làm, giá) → AI đọc, ghi vào SQLite, trừ tồn kho, xác nhận lại. Thiếu/mờ thông tin thì hỏi lại.
2. **Tư vấn hàng**: hỏi "Vios 2016 có phuộc gì?" / "đề xuất hạng mục cho 51K-123.45" → AI tra kho thật + lịch sử xe rồi trả lời.

Lệnh: `/huy <mã bill>` (huỷ + hoàn kho), `/homnay` (tổng kết ngày). Trong group, bot chỉ trả lời ảnh, tin @mention hoặc reply bot.

## Cài đặt
```
pip install -r requirements.txt
cp .env.example .env      # điền token BotFather, API key, ALLOWED_CHAT_IDS
python import_inventory.py kho_mau.csv   # nạp kho (thay bằng file kho thật)
python bot.py
```
Tắt "Group Privacy" của bot trong @BotFather (/setprivacy → Disable) để bot thấy ảnh trong group. Lấy chat id group: thêm @RawDataBot hoặc xem log bot.

## Kiểm thử
`python tests/test_tools.py` (không cần mạng/API key).

## Nối kho thật
Kho hiện đọc từ bảng `inventory` (CSV import, chạy lại để đồng bộ). Nếu kho nằm ở Google Sheet/phần mềm khác, chỉ cần thay `_search_inventory` trong `tools.py`.
