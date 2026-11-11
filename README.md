# import-product-excel-nasani

## Khảo sát và cập nhật SEO

Chương trình khảo sát/cập nhật bản ghi nằm trong `seo_updater.py` và dùng riêng
`seo_data.py`. Mặc định công cụ chỉ khảo sát; chế độ UPDATE yêu cầu xác nhận
riêng. Script `import_excel.py` không bị thay đổi. Công cụ dùng cùng Chromium
persistent profile tại `browser_profile/` để giữ phiên đăng nhập. Nếu cần đăng
nhập, hãy nhập thông tin trực tiếp trong cửa sổ trình duyệt.

Crawler chỉ đọc `seo_cli.py` là công cụ riêng; xem hướng dẫn tại
[SEO_README.md](./SEO_README.md). CLI không có chế độ ghi/cập nhật website.

```bash
.venv/bin/python seo_updater.py
```

Kết quả khảo sát và log được ghi trong `logs/seo_scan_report.json` và
`logs/seo_updater.log`. Báo cáo liệt kê module, bản ghi, trường nhận diện được,
trường SEO chưa phân loại và lỗi truy cập. Script chỉ cập nhật trường đã nhận
diện chắc chắn; các trường khác được giữ nguyên.

Sau khi xem báo cáo và xác nhận muốn cập nhật, chạy thử tối đa một bản ghi:

```bash
.venv/bin/python seo_updater.py --mode UPDATE --limit 1 \
  --record-url 'https://2tskinbar.com/admin/seopage/man/trang-chu' \
  --confirm-update
```

UPDATE một bản ghi bắt buộc có URL admin chính xác; URL phải được tìm thấy lại
trong SCAN mới và có trường SEO nhận diện duy nhất. Script yêu cầu nhập
`UPDATE ONE RECORD` trực tiếp trong terminal trước khi thực hiện. Cập nhật toàn
bộ cần một xác nhận riêng:

```bash
.venv/bin/python seo_updater.py --mode UPDATE --confirm-update --confirm-all
```

Không chạy nhiều phiên Chromium cùng lúc trên cùng `browser_profile/`. Báo cáo
UPDATE và trạng thái bỏ qua các bản ghi đã xử lý được lưu trong `logs/`.
