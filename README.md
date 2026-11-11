# NASANI — Menu luồng chính

## Cấu hình SEO lần đầu

1. Mở file `user_config.py` ở thư mục gốc.
2. Nhập website vào `WEBSITE_URL` (chỉ cần URL website, không thêm `/admin`).
3. Nhập nội dung vào 4 trường trong `SEO_DATA`.
4. Lưu file. Nếu website có URL đăng nhập riêng, khai báo `LOGIN_URL`; để trống
   nếu chưa biết, chương trình sẽ mở khu vực quản trị và không tự đoán URL đăng nhập.
5. Chạy `run_nasani.command`. Lần đầu chạy, chương trình tự cài dependency và
   Chromium nếu còn thiếu.
6. Chọn chức năng **Cập nhật nội dung SEO**.
7. Đăng nhập trực tiếp trong cửa sổ trình duyệt khi được yêu cầu.
8. Xem báo cáo SCAN trước. Chỉ xác nhận UPDATE nếu nội dung và phạm vi đúng.

Nếu trang quản trị không nằm tại `<WEBSITE_URL>/admin`, có thể khai báo `ADMIN_URL`
trong cùng file cấu hình. Không nhập mật khẩu vào file cấu hình hoặc Terminal.

Nếu macOS chặn lần mở đầu, nhấp chuột phải vào `run_nasani.command` và chọn **Mở**.

## Nhập sản phẩm từ Excel

Đây là chức năng riêng, không dùng `SEO_DATA` và không thay đổi mapping/luồng
nhập hiện có:

1. Chuẩn bị `products.xlsx` theo mapping Excel hiện có.
2. Chạy `run_nasani.command` và chọn **Nhập sản phẩm từ Excel**.
3. Đăng nhập hoặc mở form thêm sản phẩm trong trình duyệt theo lời nhắc.
4. Xem kết quả trong `import_report.csv`.

## Chạy và kiểm thử

Trong menu, chọn **Kiểm tra dự án / website** để chạy unit tests hoặc kiểm tra
form website chỉ đọc. Trước khi chạy, đóng Chrome/Chromium khác đang dùng
`browser_profile/`.

Có thể chạy kiểm thử tự động bằng lệnh:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

## Cập nhật SEO

SEO dùng một bộ nội dung trong `user_config.py` cho các bản ghi tìm được. SCAN
chỉ đọc và lưu báo cáo tại `logs/seo_scan_report.json`; không ghi dữ liệu website.
UPDATE cần xác nhận rõ ràng sau khi đã xem báo cáo SCAN. Các trường không được
nhận diện chắc chắn sẽ không bị thay đổi.

```bash
.venv/bin/python -m nasani.seo_updater
```

Xem thêm chi tiết về crawler SCAN chỉ đọc tại [SEO_README.md](./SEO_README.md).
