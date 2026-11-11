# NASANI — Menu luồng chính

## Chạy menu

```bash
.venv/bin/python main.py
```

Nếu chưa cài thư viện:

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m playwright install chromium
```

Menu gom các thao tác thường dùng:

1. **Nhập sản phẩm từ Excel** — đọc `products.xlsx` và
   xuất kết quả vào `import_report.csv`.
2. **Cập nhật SEO toàn website** — chạy SCAN trước, xem báo cáo rồi xác nhận
   `UPDATE`; nếu tiếp tục, nhập thêm chính xác `UPDATE ALL SEO RECORDS` để ghi
   dữ liệu thật lên các bản ghi có trường SEO được nhận diện.
3. **Kiểm tra dự án / website** — chạy unit test không truy cập website hoặc
   mở trình duyệt để kiểm tra thủ công. Kiểm tra trình duyệt chỉ đọc, không lưu
   dữ liệu.

## Cấu trúc

- `main.py`: điểm vào menu.
- `nasani/`: luồng nhập Excel, SEO và các module dùng chung.
- `tests/`: kiểm thử tự động, không truy cập website.
- `tools/`: công cụ kiểm tra form website bằng trình duyệt, chỉ đọc.
- `products.xlsx`: dữ liệu nhập sản phẩm.
- `browser_profile/`, `logs/`, `reports/`: dữ liệu cục bộ được tạo khi chạy.

Các luồng dùng Chromium profile tại `browser_profile/`. Đóng các cửa sổ Chrome
hoặc Chromium đang dùng profile này trước khi chạy menu. Nếu được yêu cầu đăng
nhập, hãy nhập thông tin trực tiếp trong cửa sổ trình duyệt, không đưa mật khẩu
vào terminal hay source code.

## Cập nhật SEO

SEO dùng dữ liệu trong `nasani/seo_data.py`. Hiện tại cùng một bộ nội dung được áp
dụng cho mọi bản ghi; cần chuẩn bị nội dung riêng theo từng trang nếu không
muốn SEO các trang bị trùng. Báo cáo SCAN và log được lưu trong
`logs/seo_scan_report.json` và `logs/seo_updater.log`. Công cụ chỉ cập nhật các
trường SEO nhận diện được; các trường khác được giữ nguyên.

Để chỉ khảo sát, không ghi website:

```bash
.venv/bin/python -m nasani.seo_updater
```

Để kiểm tra phạm vi trước khi cập nhật, xem báo cáo SCAN rồi chạy thử một bản
ghi đã xác định rõ:

```bash
.venv/bin/python -m nasani.seo_updater --mode UPDATE --limit 1 \
  --record-url 'https://2tskinbar.com/admin/seopage/man/trang-chu' \
  --confirm-update
```

Muốn cập nhật toàn bộ bằng lệnh trực tiếp:

```bash
.venv/bin/python -m nasani.seo_updater --mode UPDATE --confirm-update --confirm-all
```

Chạy kiểm thử tự động bằng `.venv/bin/python -m unittest discover -s tests -v`.
Xem thêm hướng dẫn crawler chỉ đọc tại [SEO_README.md](./SEO_README.md).
