import argparse
import hashlib
import json
import logging
import re
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from seo_data import SEO_DATA
from seo_field_detector import detect_seo_fields, unique_field_locator
from seo_report import save_report, update_summary
from seo_scanner import safe_url


BASE_DIR = Path(__file__).resolve().parent
PROFILE_DIR = BASE_DIR / "browser_profile"
LOG_DIR = BASE_DIR / "logs"
SCAN_REPORT_PATH = LOG_DIR / "seo_scan_report.json"
UPDATE_REPORT_PATH = LOG_DIR / "seo_update_report.json"
UPDATE_STATE_PATH = LOG_DIR / "seo_update_state.json"
LOGIN_URL = "https://2tskinbar.com/admin/user/login"
ADMIN_URL = "https://2tskinbar.com/admin"
MODE = "SCAN"
PAGE_TIMEOUT_MS = 30000
LOGIN_WAIT_SECONDS = 1200
RECORD_LINK_PATTERN = re.compile(r"/admin/.*/edit/", re.IGNORECASE)

LOGGER = logging.getLogger("seo_updater")


class LoginRequired(RuntimeError):
    pass


def configure_logging():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    LOGGER.setLevel(logging.INFO)
    LOGGER.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(message)s"
    )
    file_handler = logging.FileHandler(
        LOG_DIR / "seo_updater.log",
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    LOGGER.addHandler(file_handler)
    LOGGER.addHandler(stream_handler)


def validate_seo_data():
    required_keys = {
        "seo_title",
        "seo_keywords",
        "seo_description",
        "primary_keyword",
    }
    if set(SEO_DATA) != required_keys:
        raise ValueError(
            "seo_data.py phải khai báo đúng 4 khóa: "
            + ", ".join(sorted(required_keys))
        )

    for key, value in SEO_DATA.items():
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                "Giá trị {} phải là chuỗi không rỗng.".format(key)
            )
    if len(SEO_DATA["seo_keywords"]) > 70:
        LOGGER.warning(
            "SEO Keywords có %s ký tự; giao diện gợi ý tối đa 70. "
            "Giữ nguyên dữ liệu, không tự cắt.",
            len(SEO_DATA["seo_keywords"]),
        )
    if len(SEO_DATA["seo_description"]) > 160:
        LOGGER.warning(
            "SEO Description có %s ký tự; giao diện gợi ý tối đa 160. "
            "Giữ nguyên dữ liệu, không tự cắt.",
            len(SEO_DATA["seo_description"]),
        )
    if SEO_DATA["primary_keyword"].casefold() not in SEO_DATA["seo_title"].casefold():
        LOGGER.warning(
            "SEO Title chưa chứa nguyên cụm primary_keyword theo so sánh không phân biệt hoa thường."
        )


def is_login_page(page):
    return urlparse(page.url).path.rstrip("/") == "/admin/user/login"


def navigate_page(page, url):
    response = page.goto(
        url,
        wait_until="domcontentloaded",
        timeout=PAGE_TIMEOUT_MS,
    )
    ensure_authenticated(page)
    if response is not None and response.status >= 400:
        raise RuntimeError(
            "Trang trả về HTTP {}: {}".format(response.status, page.url)
        )
    return response


def wait_for_login(page):
    page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
    if page.locator("#layout-menu").count() > 0:
        page.goto(ADMIN_URL, wait_until="domcontentloaded")
        return

    LOGGER.info(
        "Đang chờ đăng nhập thủ công trong cửa sổ Chromium. "
        "Không nhập mật khẩu vào terminal hoặc source."
    )
    print(
        "\nTrình duyệt đang mở trang đăng nhập Nasani. "
        "Hãy đăng nhập trực tiếp trong cửa sổ trình duyệt."
    )
    deadline = time.monotonic() + LOGIN_WAIT_SECONDS
    while time.monotonic() < deadline:
        page.wait_for_timeout(1000)
        if not is_login_page(page) and page.locator("#layout-menu").count() > 0:
            LOGGER.info("Đã phát hiện phiên admin sau khi đăng nhập thủ công.")
            page.goto(ADMIN_URL, wait_until="domcontentloaded")
            return

    raise LoginRequired(
        "Hết thời gian chờ đăng nhập. Không có dữ liệu website nào được sửa."
    )


def ensure_authenticated(page):
    if is_login_page(page):
        raise LoginRequired(
            "Website yêu cầu đăng nhập lại; dừng để người dùng xử lý."
        )


def _module_name(anchor):
    text = re.sub(r"\s+", " ", (anchor.get("text") or "")).strip()
    if text:
        return text
    parts = [part for part in urlparse(anchor["url"]).path.split("/") if part]
    return parts[-1].replace("-", " ").title() if parts else "Admin module"


def discover_modules(page):
    navigate_page(page, ADMIN_URL)
    ensure_authenticated(page)
    anchors = page.locator("a[href]").evaluate_all(
        """elements => elements.map(a => ({
            url: a.href,
            text: (a.innerText || a.textContent || '').trim()
                .replace(/\\s+/g, ' ')
        }))"""
    )
    modules = {}
    for anchor in anchors:
        parsed = urlparse(anchor["url"])
        if parsed.netloc != "2tskinbar.com":
            continue
        if not parsed.path.startswith("/admin/"):
            continue
        if parsed.path in (
            "/admin/user/logout",
            "/admin/delete-cache",
        ):
            continue
        if "changepass" in parsed.query:
            continue

        canonical_url = parsed._replace(query="", fragment="").geturl()
        if canonical_url == ADMIN_URL + "/":
            continue
        modules.setdefault(canonical_url, {
            "name": _module_name(anchor),
            "url": canonical_url,
        })

    return list(modules.values())


def extract_editable_rows(page):
    rows = page.locator("table tbody tr").evaluate_all(
        """rows => rows.map(row => {
            const links = Array.from(row.querySelectorAll('a[href]'))
                .map(a => ({
                    url: a.href,
                    text: (a.innerText || a.title || '').trim()
                        .replace(/\\s+/g, ' ')
                }));
            const editLinks = links.filter(link =>
                /\\/admin\\/.*\\/edit\\//i.test(link.url) ||
                /chinh sua|edit/i.test(link.text)
            );
            const nameLink = links.find(link =>
                link.text && !/view|copy|chinh sua|edit|xoa|delete/i.test(link.text)
            );
            return {
                title: nameLink ? nameLink.text : '',
                edit_urls: editLinks.map(link => link.url)
            };
        })"""
    )

    unique = {}
    for row in rows:
        for edit_url in row["edit_urls"]:
            parsed = urlparse(edit_url)
            if parsed.netloc != "2tskinbar.com":
                continue
            if not RECORD_LINK_PATTERN.search(parsed.path):
                continue
            unique.setdefault(edit_url, row.get("title") or "")
    return unique


def count_table_rows(page):
    return page.locator("table tbody tr").evaluate_all(
        """rows => rows.filter(row => {
            const text = (row.innerText || '').trim().replace(/\\s+/g, ' ').toLowerCase();
            if (!text) return false;
            return ![
                'không có dữ liệu',
                'khong co du lieu',
                'no data',
                'no records',
                'no matching records'
            ].includes(text);
        }).length"""
    )


def pagination_urls(page, current_url):
    urls = page.locator(
        ".pagination a[href], ul.pagination a[href], a.page-link[href]"
    ).evaluate_all("(elements) => elements.map(a => a.href)")
    current = urlparse(current_url)
    found = []
    for url in urls:
        parsed = urlparse(url)
        if parsed.netloc != current.netloc or parsed.path != current.path:
            continue
        if parse_qs(parsed.query).get("page") == parse_qs(current.query).get("page"):
            continue
        if url not in found:
            found.append(url)
    return found


def read_record_title(page, fallback, content_module):
    if content_module:
        title_field = page.locator("#namevi")
        if title_field.count() == 1 and title_field.is_visible():
            value = title_field.input_value().strip()
            if value:
                return value

        headings = page.locator("h1, h2, h3, h4").all_inner_texts()
        for heading in headings:
            if heading.strip():
                return heading.strip()[:160]

    return fallback[:160] if fallback else "Bản ghi"


def _record_is_content_module(url):
    return any(
        segment in urlparse(url).path
        for segment in (
            "/product/",
            "/product-list/",
            "/news/",
            "/static/",
            "/seopage/",
        )
    )


def _record_id(url, ordinal):
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    if query.get("id"):
        return query["id"][0]
    match = re.search(r"/edit/([^/]+)", parsed.path)
    if match:
        return match.group(1)
    return str(ordinal)


def _record_report(module, edit_url, title, page, scan_status):
    is_seopage = "/seopage/" in urlparse(page.url).path
    fields, unrecognized = detect_seo_fields(page, is_seopage=is_seopage)
    seo_fields = {
        key: values
        for key, values in fields.items()
    }
    if seo_fields:
        status = "SCANNED"
    elif unrecognized:
        status = "UNRECOGNIZED_SEO_FIELDS"
    else:
        status = scan_status

    return {
        "module": module["name"],
        "module_url": module["url"],
        "name": title,
        "edit_url": edit_url,
        "seo_fields": seo_fields,
        "unrecognized_fields": unrecognized,
        "scan_status": status,
        "update_status": None,
        "error": None,
    }


def scan_module(page, module):
    module_report = {
        "name": module["name"],
        "url": module["url"],
        "accessible": False,
        "editable": False,
        "record_count": 0,
        "records_opened": 0,
        "table_rows_observed": 0,
        "unprocessed_record_count": 0,
        "records_with_seo_fields": 0,
        "error": None,
    }
    records = []
    pages_to_scan = [module["url"]]
    visited_pages = set()
    edit_rows = {}

    while pages_to_scan:
        list_url = pages_to_scan.pop(0)
        if list_url in visited_pages:
            continue
        visited_pages.add(list_url)
        navigate_page(page, list_url)
        module_report["accessible"] = True

        current_url = page.url
        module_report["table_rows_observed"] += count_table_rows(page)
        rows = extract_editable_rows(page)
        for edit_url, title in rows.items():
            edit_rows.setdefault(edit_url, title)
        for page_url in pagination_urls(page, current_url):
            if page_url not in visited_pages and page_url not in pages_to_scan:
                pages_to_scan.append(page_url)

        if not rows:
            is_seopage = "/seopage/" in urlparse(current_url).path
            fields, unrecognized = detect_seo_fields(
                page,
                is_seopage=is_seopage,
            )
            if fields or unrecognized:
                records.append(_record_report(
                    module,
                    current_url,
                    module["name"],
                    page,
                    "NO_SEO_FIELDS",
                ))
                module_report["editable"] = True

    content_module = _record_is_content_module(module["url"])
    for ordinal, (edit_url, fallback_title) in enumerate(
        edit_rows.items(),
        start=1,
    ):
        try:
            navigate_page(page, edit_url)
            title = read_record_title(page, fallback_title, content_module)
            if not content_module:
                title = "Bản ghi {}".format(_record_id(edit_url, ordinal))
            record = _record_report(
                module,
                edit_url,
                title,
                page,
                "NO_SEO_FIELDS",
            )
            records.append(record)
            module_report["editable"] = True
        except LoginRequired:
            raise
        except Exception as error:
            records.append({
                "module": module["name"],
                "module_url": module["url"],
                "name": (
                    fallback_title[:160]
                    if content_module and fallback_title
                    else "Bản ghi {}".format(_record_id(edit_url, ordinal))
                ),
                "edit_url": edit_url,
                "seo_fields": {},
                "unrecognized_fields": [],
                "scan_status": "FAILED",
                "update_status": None,
                "error": str(error),
            })
            LOGGER.exception(
                "Không khảo sát được bản ghi %s; tiếp tục bản ghi khác.",
                edit_url,
            )

    if edit_rows:
        module_report["record_count"] = len(edit_rows)
        module_report["records_opened"] = len(edit_rows)
    elif records:
        module_report["record_count"] = len(records)
        module_report["records_opened"] = len(records)
    else:
        module_report["record_count"] = module_report["table_rows_observed"]
        module_report["unprocessed_record_count"] = (
            module_report["table_rows_observed"]
        )

    module_report["records_with_seo_fields"] = sum(
        1 for record in records if record["seo_fields"]
    )
    return module_report, records


def scan_website(page):
    modules = discover_modules(page)
    report = {
        "mode": "SCAN",
        "website": "https://2tskinbar.com",
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "modules": [],
        "records": [],
        "unprocessed": [],
        "summary": {},
    }

    if not modules:
        raise RuntimeError(
            "Không tìm thấy route module nào trong menu admin."
        )

    LOGGER.info("Bắt đầu SCAN %s module.", len(modules))
    for index, module in enumerate(modules, start=1):
        module_records = []
        LOGGER.info(
            "SCAN module %s/%s: %s (%s)",
            index,
            len(modules),
            module["name"],
            module["url"],
        )
        try:
            module_report, module_records = scan_module(page, module)
            report["modules"].append(module_report)
            report["records"].extend(module_records)
            LOGGER.info(
                "Hoàn tất module %s: %s bản ghi, %s có trường SEO.",
                module["name"],
                module_report["record_count"],
                module_report["records_with_seo_fields"],
            )
        except LoginRequired:
            raise
        except Exception as error:
            module_report = {
                "name": module["name"],
                "url": module["url"],
                "accessible": False,
                "editable": False,
                "record_count": 0,
                "records_opened": 0,
                "table_rows_observed": 0,
                "unprocessed_record_count": 0,
                "records_with_seo_fields": 0,
                "error": str(error),
            }
            report["modules"].append(module_report)
            module_records = []
            report["unprocessed"].append({
                "module": module["name"],
                "url": module["url"],
                "reason": str(error),
            })
            LOGGER.exception(
                "Không khảo sát được module %s; tiếp tục module kế tiếp.",
                module["name"],
            )
        report["unprocessed"].extend(
            {
                "module": record["module"],
                "url": record["edit_url"],
                "reason": record["error"],
            }
            for record in module_records
            if record.get("error")
        )
        if module_report.get("unprocessed_record_count"):
            report["unprocessed"].append({
                "module": module["name"],
                "url": module["url"],
                "record_count": module_report["unprocessed_record_count"],
                "reason": (
                    "Có hàng trong danh sách nhưng không tìm thấy link "
                    "chỉnh sửa để khảo sát form."
                ),
            })
        update_summary(report)
        save_report(report, SCAN_REPORT_PATH)

    report["completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    update_summary(report)
    save_report(report, SCAN_REPORT_PATH)
    LOGGER.info(
        "SCAN hoàn tất: %s module, %s bản ghi, %s có trường SEO. Báo cáo: %s",
        report["summary"]["total_modules"],
        report["summary"]["total_records"],
        report["summary"]["records_with_seo_fields"],
        SCAN_REPORT_PATH,
    )
    return report


def _target_fingerprint():
    payload = json.dumps(
        SEO_DATA,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load_update_state():
    if not UPDATE_STATE_PATH.exists():
        return {}
    with UPDATE_STATE_PATH.open("r", encoding="utf-8") as file:
        state = json.load(file)
    if not isinstance(state, dict):
        raise ValueError("File trạng thái cập nhật SEO không hợp lệ.")
    return state


def _save_update_state(state):
    save_report(state, UPDATE_STATE_PATH)


def _read_locator_value(locator):
    return locator.input_value()


def update_record(page, record):
    edit_url = record["edit_url"]
    navigate_page(page, edit_url)
    is_seopage = "/seopage/" in urlparse(page.url).path
    detected, unrecognized = detect_seo_fields(page, is_seopage=is_seopage)
    record["unrecognized_fields"] = unrecognized

    targets = []
    for key, fields in detected.items():
        if len(fields) != 1:
            raise RuntimeError(
                "Trường {} xuất hiện {} lần; không thể xác định duy nhất."
                .format(key, len(fields))
            )
        locator = unique_field_locator(page, fields[0])
        if locator is None:
            raise RuntimeError(
                "Không xác định được locator duy nhất cho trường {}."
                .format(key)
            )
        if key not in SEO_DATA:
            continue
        targets.append((key, fields[0], locator, SEO_DATA[key]))

    if not targets:
        record["update_status"] = "FAILED_NO_RECOGNIZED_FIELDS"
        record["error"] = "Không có trường SEO được nhận diện chắc chắn."
        return

    original_values = {
        key: _read_locator_value(locator)
        for key, _field, locator, _target in targets
    }
    if all(original_values[key] == target for key, _field, _loc, target in targets):
        record["update_status"] = "ALREADY_CURRENT"
        record["error"] = None
        return

    for key, _field, locator, target in targets:
        locator.fill("")
        locator.fill(target)
        if _read_locator_value(locator) != target:
            raise RuntimeError(
                "Đọc lại sau khi nhập không khớp ở trường {}.".format(key)
            )

    save_buttons = page.locator(
        "button[name='button-out'], "
        "input[name='button-out'], "
        "button[type='submit'], "
        "input[type='submit']"
    )
    save_button = None
    for index in range(save_buttons.count()):
        candidate = save_buttons.nth(index)
        if not candidate.is_visible() or not candidate.is_enabled():
            continue
        if candidate.evaluate("(el) => el.tagName.toLowerCase()") == "input":
            label = (candidate.get_attribute("value") or "").strip()
        else:
            label = candidate.inner_text().strip()
        if label.lower() in ("lưu", "luu"):
            save_button = candidate
            break

    if save_button is None:
        raise RuntimeError("Không tìm thấy nút Lưu chính xác trên form.")

    save_button.click(timeout=10000)
    page.wait_for_timeout(1500)
    ensure_authenticated(page)

    navigate_page(page, edit_url)
    readback, readback_unknown = detect_seo_fields(
        page,
        is_seopage=is_seopage,
    )
    record["unrecognized_fields"] = readback_unknown

    for key, _field, _locator, target in targets:
        fields = readback.get(key, [])
        if len(fields) != 1:
            raise RuntimeError(
                "Không thể xác minh duy nhất trường {} sau khi lưu."
                .format(key)
            )
        locator = unique_field_locator(page, fields[0])
        if locator is None or _read_locator_value(locator) != target:
            raise RuntimeError(
                "Giá trị lưu lại không khớp ở trường {}.".format(key)
            )

    record["update_status"] = "UPDATED_VERIFIED"
    record["error"] = None


def update_records(page, report, limit=None):
    state = _load_update_state()
    fingerprint = _target_fingerprint()
    records = [
        record for record in report["records"]
        if record.get("seo_fields")
    ]
    if limit is not None:
        records = records[:limit]

    for index, record in enumerate(records, start=1):
        state_key = record["edit_url"]
        previous = state.get(state_key, {})
        if previous.get("fingerprint") == fingerprint:
            LOGGER.info(
                "Đã có trạng thái thành công; đọc lại trước để tránh ghi lặp: %s",
                record["edit_url"],
            )

        LOGGER.info(
            "UPDATE %s/%s: %s (%s)",
            index,
            len(records),
            record["name"],
            record["edit_url"],
        )
        try:
            update_record(page, record)
            if record["update_status"] in (
                "UPDATED_VERIFIED",
                "ALREADY_CURRENT",
            ):
                state[state_key] = {
                    "fingerprint": fingerprint,
                    "status": record["update_status"],
                    "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                }
                _save_update_state(state)
            else:
                LOGGER.error(
                    "Không cập nhật được %s: %s",
                    record["edit_url"],
                    record.get("error"),
                )
        except LoginRequired:
            record["update_status"] = "FAILED_LOGIN_REQUIRED"
            record["error"] = "Phiên admin hết hạn; dừng để đăng nhập lại."
            raise
        except Exception as error:
            record["update_status"] = "FAILED"
            record["error"] = str(error)
            LOGGER.exception("Lỗi cập nhật bản ghi %s.", record["edit_url"])

        update_summary(report)
        save_report(report, UPDATE_REPORT_PATH)

    report["mode"] = "UPDATE"
    report["completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    update_summary(report)
    save_report(report, UPDATE_REPORT_PATH)
    LOGGER.info("Báo cáo UPDATE: %s", UPDATE_REPORT_PATH)


def _validate_record_url(record_url):
    normalized = safe_url(record_url, record_url)
    if normalized is None:
        raise ValueError(
            "--record-url phải là URL HTTPS an toàn trong /admin "
            "của 2tskinbar.com."
        )
    return normalized


def _select_update_records(records, record_url=None, limit=None):
    if record_url is not None:
        selected = [
            record for record in records
            if record.get("edit_url") == record_url
            and record.get("seo_fields")
        ]
        if len(selected) != 1:
            raise RuntimeError(
                "SCAN mới phải tìm thấy đúng một bản ghi có trường SEO tại "
                "--record-url; tìm thấy {}.".format(len(selected))
            )
        return selected
    selected = [record for record in records if record.get("seo_fields")]
    return selected[:limit] if limit is not None else selected


def parse_args():
    parser = argparse.ArgumentParser(
        description="Khảo sát và cập nhật các trường SEO trên Nasani."
    )
    parser.add_argument(
        "--mode",
        choices=("SCAN", "UPDATE"),
        default=MODE,
        help="SCAN chỉ khảo sát (mặc định); UPDATE cần xác nhận rõ ràng.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Giới hạn số bản ghi UPDATE; dùng --limit 1 để chạy thử.",
    )
    parser.add_argument(
        "--confirm-update",
        action="store_true",
        help="Xác nhận chủ động chế độ UPDATE.",
    )
    parser.add_argument(
        "--confirm-all",
        action="store_true",
        help="Cho phép UPDATE tất cả bản ghi SEO tìm thấy.",
    )
    parser.add_argument(
        "--record-url",
        default=None,
        help="URL admin chính xác của bản ghi cần cập nhật; bắt buộc cho --limit 1.",
    )
    return parser.parse_args()


def confirm_update(args):
    if not args.confirm_update:
        raise RuntimeError(
            "UPDATE bị chặn. Thêm --confirm-update sau khi đã xem báo cáo SCAN."
        )
    if args.limit is None and not args.confirm_all:
        raise RuntimeError(
            "UPDATE toàn bộ bị chặn. Dùng --limit 1 để thử hoặc "
            "thêm --confirm-all sau khi đã xác nhận."
        )
    if args.limit is not None and args.limit < 1:
        raise ValueError("--limit phải lớn hơn 0.")
    if args.limit == 1 and not args.record_url:
        raise RuntimeError(
            "Không cập nhật bản ghi tùy ý. Cần chỉ định --record-url."
        )
    if args.record_url:
        args.record_url = _validate_record_url(args.record_url)
        if args.limit != 1:
            raise RuntimeError(
                "--record-url chỉ được dùng cùng --limit 1."
            )

    expected = (
        "UPDATE ONE RECORD"
        if args.limit == 1
        else "UPDATE ALL SEO RECORDS"
    )
    if not sys.stdin.isatty():
        raise RuntimeError("UPDATE cần terminal tương tác để xác nhận lần cuối.")
    answer = input(
        "Xác nhận nhập chính xác '{}': ".format(expected)
    ).strip()
    if answer != expected:
        raise RuntimeError("Không xác nhận UPDATE; không ghi dữ liệu website.")


def main():
    args = parse_args()
    configure_logging()
    validate_seo_data()

    if args.mode == "UPDATE":
        confirm_update(args)

    with sync_playwright() as playwright:
        try:
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=str(PROFILE_DIR),
                headless=False,
                viewport={"width": 1440, "height": 950},
            )
        except Exception as error:
            raise RuntimeError(
                "Không thể mở browser_profile. Đóng các Chromium/Chrome đang "
                "dùng profile này rồi thử lại. Lỗi: {}".format(error)
            ) from error

        try:
            page = context.pages[0] if context.pages else context.new_page()
            wait_for_login(page)
            report = scan_website(page)
            if args.mode == "UPDATE":
                records = _select_update_records(
                    report["records"],
                    record_url=args.record_url,
                    limit=args.limit,
                )
                targeted_report = dict(report)
                targeted_report["records"] = records
                update_limit = 1 if args.record_url else args.limit
                update_records(page, targeted_report, limit=update_limit)
            print("\nHoàn tất {}.".format(args.mode))
            print("Báo cáo SCAN: {}".format(SCAN_REPORT_PATH))
            if args.mode == "UPDATE":
                print("Báo cáo UPDATE: {}".format(UPDATE_REPORT_PATH))
        finally:
            context.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nĐã dừng theo yêu cầu.")
        raise SystemExit(130)
    except Exception as error:
        LOGGER.exception("Chương trình kết thúc với lỗi.")
        print("\nLỖI: {}".format(error))
        raise SystemExit(1)
