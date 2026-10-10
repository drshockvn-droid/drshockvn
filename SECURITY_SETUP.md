# Hướng dẫn chuyển DrShockVN sang đăng nhập bằng Email (Firebase Auth)

Làm **đúng thứ tự** để app không bị gián đoạn. Trước khi bắt đầu: Realtime Database > Data > ⋮ > **Export JSON** để sao lưu.

## 1. Bật đăng nhập Email/Mật khẩu
Firebase Console > Authentication > Sign-in method > **Email/Password** > Enable.

## 2. Tạo tài khoản Chủ Xưởng đầu tiên
1. Authentication > Users > **Add user** (email + mật khẩu mạnh). Sao chép **User UID**.
2. Realtime Database > Data > bấm `+` ở gốc, tạo nút `roles` > bên trong thêm khóa = UID vừa sao chép, giá trị = `admin` (dạng chuỗi).
   Kết quả: `roles / <UID> : "admin"`

## 3. Đưa bản `index.html` mới lên (merge branch này rồi deploy)
Sau khi deploy, đăng nhập bằng tài khoản Chủ Xưởng. App tự tạo hồ sơ cho bạn và **xóa mã PIN cũ** khỏi `garage/staff`.

## 4. Tạo tài khoản nhân viên
Tab **Nhân sự** > **+ Thêm Nhân Viên**: nhập tên, vai trò, email, mật khẩu ban đầu (≥ 8 ký tự). Nhân viên dùng nút "Quên mật khẩu?" ở màn hình đăng nhập để tự đặt lại. Xóa hồ sơ PIN cũ (hiển thị chữ đỏ) sau khi đã tạo tài khoản mới.

## 5. Áp dụng Rules (SAU khi bước 2-4 xong)
Realtime Database > Rules > dán nội dung `database.rules.json` > **Publish**. Từ lúc này người chưa đăng nhập không đọc/ghi được gì. Máy nào còn mở bản app cũ sẽ ngừng đồng bộ cho tới khi tải lại.

## 6. Làm thêm
- Xuất backup rồi **xóa nhánh cũ `drshock_garage_data`** nếu không còn dùng.
- **App Check**: Firebase Console > App Check > đăng ký web app với reCAPTCHA v3, dán site key vào `APP_CHECK_SITE_KEY` trong `index.html`, rồi bật Enforce cho Realtime Database.
- Google Cloud Console > APIs & Services > Credentials: giới hạn API key theo HTTP referrer (tên miền chạy app) và chỉ cho các API cần thiết.
- Đăng xuất khỏi máy dùng chung. Thu hồi nhân viên nghỉ việc: xóa ở tab Nhân sự (thu hồi quyền ngay) rồi xóa tài khoản trong Authentication.

## Phân quyền trong rules
| Dữ liệu | Đọc | Ghi |
|---|---|---|
| kho, hóa đơn, nhật ký kho, meta | mọi nhân viên | mọi nhân viên (tech lập bill phải trừ kho) |
| phiếu nhập, ảnh sản phẩm, thông báo | mọi nhân viên | admin, stock |
| nhân sự, hồ sơ garage, cấu hình AI | mọi nhân viên | admin |
| tài chính | admin | admin |
| `roles` | chính mình / admin | admin |

Lưu ý: `garage/aiConfig` chứa API key AI mà mọi nhân viên đọc được (app cần để dùng trợ lý). Nên đổi sang gọi AI qua Cloud Function về sau.
