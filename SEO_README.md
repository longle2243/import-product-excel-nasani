# NASANI SEO — SCAN chỉ đọc

## Thành phần

- `nasani/seo_cli.py` và `nasani/seo_scanner.py`: crawler chỉ đọc, giới hạn trong các liên kết
  an toàn tìm thấy trên trang admin.
- `nasani/seo_field_detector.py`: nhận diện trường SEO; `nasani/seo_detector.py` là adapter
  cho scanner.
- `nasani/browser_manager.py`: mở Chromium với profile hiện có và chờ đăng nhập thủ công.
- `nasani/report_manager.py`: lưu checkpoint JSON và xuất CSV.
- `nasani/seo_updater.py` có chế độ UPDATE được bảo vệ bằng xác
  nhận rõ ràng. CLI bên dưới không gọi UPDATE.
- Website và dữ liệu SEO được đọc từ `user_config.py` ở thư mục gốc.

## Chạy tại máy có profile

Cài dependency bằng đúng Python của môi trường dự án:

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m playwright install chromium
.venv/bin/python -m nasani.seo_cli
```

Không xóa hoặc tạo lại `browser_profile`. Đóng phiên Chromium/Chrome khác đang
dùng profile này trước khi chạy. Có thể chỉ định profile ở nơi khác:

```bash
.venv/bin/python -m nasani.seo_cli --profile /duong/dan/browser_profile
.venv/bin/python -m nasani.seo_cli --profile /duong/dan/browser_profile --resume
```

Menu Enter = SCAN; lựa chọn UPDATE trong CLI sẽ dừng mà không ghi lên website.
Đăng nhập trực tiếp trong cửa sổ trình duyệt rồi nhấn Enter tại terminal.
Nếu `LOGIN_URL` để trống, chương trình không tự đoán URL đăng nhập; hãy mở trang
đăng nhập trong trình duyệt nếu website không tự chuyển hướng.
Mật khẩu không được nhập vào terminal hoặc lưu trong source code. Profile thiếu
hoặc trống sẽ bị từ chối, không tự khởi tạo.

## Báo cáo và giới hạn

- `reports/scan_report.json`: pages, trường SEO nhận diện hoặc chưa phân loại,
  giá trị, locator, lỗi, pending, excluded_links, blocked_requests, summary và
  limitations.
- `reports/scan_report.csv`: một dòng mỗi trường liên quan SEO; trang không có
  trường vẫn có dòng.
- `logs/scan.log`: hoạt động và lỗi, không ghi mật khẩu.
- Checkpoint JSON ghi nguyên tử sau từng trang. `--resume` bỏ qua trang đã quét;
  lỗi đã ghi trong pages cần xem riêng, không tự retry vô hạn.
- Chỉ tiếp tục checkpoint thuộc cùng `WEBSITE_URL`; nếu đổi website, hãy chạy
  SCAN mới không kèm `--resume`.
- Retry tải tối đa hai lần mỗi trang. Mặc định giới hạn 1000 trang một lượt.
- Chỉ theo href cùng origin trong `/admin`; gồm pagination có href và menu con
  đã hiện trong DOM. Không suy đoán URL module hoặc selector cụ thể CMS.
- Chỉ click ARIA tab SEO có cấu trúc không submit, không onclick.
- SCAN không fill, không submit, không gọi nút Lưu. Sau đăng nhập, chặn request
  ngoài GET/HEAD/OPTIONS và các route hành động nguy hiểm nhận diện được.
- Đây là lớp bảo vệ bảo thủ, không thể chứng minh một endpoint GET tùy ý không
  có side effect. Cần đối chiếu route CMS thực tế; ưu tiên tài khoản chỉ đọc nếu
  CMS hỗ trợ. AJAX POST dùng để đọc cũng bị chặn và ghi trong báo cáo.
- Không khẳng định quét toàn bộ: JS-only pagination/menu, iframe, tab SEO không
  theo ARIA, filter và module không có liên kết cần khảo sát tiếp bằng DOM thực tế.
- Summary đếm trang có SEO, không tuyên bố là số bản ghi duy nhất: cùng một bản
  ghi có thể có nhiều URL. Tên module/record hiện suy ra từ nhãn liên kết; cần
  đối chiếu bảng dữ liệu và record ID sau khảo sát.
- `unrecognized_fields` đếm các trường SEO chưa phân loại, không phải số trường
  SEO chắc chắn bị bỏ sót.
- Báo cáo chứa giá trị đọc được từ form, nên giữ riêng tư và không commit báo cáo.

## Kiểm chứng

Chạy kiểm thử đơn vị bằng:

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m compileall -q main.py nasani tests tools
```

Kiểm thử không truy cập website. SCAN thực tế cần profile đăng nhập và Chromium
được cài đặt; chưa thể xác nhận độ bao phủ trên CMS nếu chưa chạy ở trình duyệt.
