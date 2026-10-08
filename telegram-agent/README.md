# Dr.ShockVN — AI trưởng nhóm Telegram

Bot trong group nội bộ garage, dùng **chung database Firebase với webapp** (`garage/inventory`, `garage/invoices`, `garage/stockLogs`):
1. **Ghi bill**: nhân viên gửi ảnh xe + chú thích (biển số, dòng xe, việc làm, giá) → AI đọc, ghi hoá đơn `INV-xxx` đúng định dạng webapp (hiện ngay trong tab hoá đơn), tự trừ tồn kho và ghi nhật ký kho. Thiếu/mờ thông tin thì hỏi lại.
2. **Tư vấn hàng**: hỏi "Vios 2016 có phuộc gì?" / "đề xuất hạng mục cho 51K-123.45" → AI tra tồn kho thật + lịch sử xe rồi trả lời. Không bao giờ lộ giá vốn.

Lệnh: `/huy INV-xxx` (xoá bill + hoàn kho, giống nút xoá hoá đơn của webapp), `/homnay` (tổng kết ngày). Trong group, bot chỉ trả lời ảnh, tin @mention hoặc reply bot.

## Cài đặt
1. @BotFather: tạo bot, lấy token; `/setprivacy` → Disable để bot thấy ảnh trong group.
2. Firebase Console → Project settings → Service accounts → **Generate new private key**, lưu thành `firebase-service-account.json` (đã được .gitignore, đừng commit). Admin SDK bỏ qua security rules nên không cần mở rules công khai.
3. `pip install -r requirements.txt && cp .env.example .env` rồi điền token, API key, `ALLOWED_CHAT_IDS`.
4. `python bot.py`

## Kiểm thử
`python tests/test_tools.py` (dữ liệu giả trong bộ nhớ, không cần mạng/API key).

## Lưu ý
- Kho webapp **không có cột tương thích xe**, nên "hợp xe" chỉ suy từ tên mã hàng (vd "Phuộc sau KYB Vios 2014-2018"). Đặt tên mã hàng có dòng xe + đời xe càng đủ thì bot tư vấn càng đúng.
- Webapp ghi cả mảng bằng `set(...)`. Bot dùng transaction nên không đè dữ liệu nhau, nhưng nếu ai đó đang mở webapp offline lâu rồi lưu thì có thể ghi đè thay đổi của bot (rủi ro sẵn có của webapp).
- Hoá đơn và tồn kho là 2 nhánh riêng, không có ghi nguyên tử: nếu lỗi mạng giữa chừng, bill có thể đã ghi mà tồn chưa trừ (xem `/homnay` và Lịch sử kho để đối chiếu).
