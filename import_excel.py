
import csv
import re
import time
import unicodedata
from pathlib import Path

from openpyxl import load_workbook
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


# =========================
# CAU HINH
# =========================

BASE_DIR = Path(__file__).resolve().parent
EXCEL_FILE = BASE_DIR / "products.xlsx"
PROFILE_DIR = BASE_DIR / "browser_profile"
REPORT_FILE = BASE_DIR / "import_report.csv"

LOGIN_URL = (
    "https://demo44.nasanivietnam.net/2026/thang10/"
    "beauutypharma_1783126w/admin/user/login"
)

# None = chay tat ca san pham
# So 1 = chi thu 1 san pham
MAX_PRODUCTS = None

START_EXCEL_ROW = 2
WAIT_AFTER_SAVE_SECONDS = 5

CATEGORY_MAP = {
    "CHAM SOC DA": "1",
    "LAM SANG DA": "2",
    "DA MUN NHON": "3",
    "CHONG LAO HOA": "4",
    "CHAM SOC BODY": "5",
}

DEFAULT_CATEGORY = "0"


# =========================
# XU LY DU LIEU
# =========================

def normalize_text(value):
    value = str(value or "").strip().upper()
    value = value.replace("Đ", "D")
    value = unicodedata.normalize("NFD", value)
    value = "".join(
        char for char in value
        if unicodedata.category(char) != "Mn"
    )
    value = re.sub(r"[^A-Z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def make_slug(value):
    value = str(value or "").strip().lower()
    value = value.replace("đ", "d")
    value = unicodedata.normalize("NFD", value)
    value = "".join(
        char for char in value
        if unicodedata.category(char) != "Mn"
    )
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def text_or_space(value):
    if value is None or not str(value).strip():
        return " "
    return str(value).strip()


def price_to_text(value):
    if value is None or str(value).strip() == "":
        return ""

    if isinstance(value, bool):
        raise ValueError("Gia khong hop le")

    if isinstance(value, int):
        return str(value)

    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return str(value)

    value = str(value).strip()
    value = value.replace("₫", "").replace("đ", "")
    value = value.replace(" ", "").replace(",", "").replace(".", "")

    if value == "":
        return ""

    if not value.isdigit():
        raise ValueError(f"Gia khong hop le: {value}")

    return value


def read_products():
    if not EXCEL_FILE.exists():
        raise FileNotFoundError(
            f"Khong tim thay file Excel: {EXCEL_FILE}"
        )

    workbook = load_workbook(
        EXCEL_FILE,
        read_only=True,
        data_only=True
    )
    sheet = workbook.active

    headers = {}
    for col in range(1, sheet.max_column + 1):
        header = sheet.cell(1, col).value
        if header is not None:
            headers[str(header).strip().lower()] = col

    required = [
        "name",
        "slug",
        "category_level_1",
        "description",
        "content",
        "regular_price",
        "sale_price",
    ]

    missing = [name for name in required if name not in headers]
    if missing:
        workbook.close()
        raise ValueError(
            "Excel thieu cot: " + ", ".join(missing)
        )

    products = []

    for row_num in range(START_EXCEL_ROW, sheet.max_row + 1):
        def get_value(column_name):
            return sheet.cell(
                row_num, headers[column_name]
            ).value

        name = text_or_space(get_value("name"))

        if name.strip() == "":
            continue

        raw_slug = get_value("slug")
        slug = str(raw_slug).strip() if raw_slug else ""
        if not slug:
            slug = make_slug(name)

        category_name = str(
            get_value("category_level_1") or ""
        ).strip()
        category_value = CATEGORY_MAP.get(
            normalize_text(category_name),
            DEFAULT_CATEGORY
        )

        if category_name and category_value == DEFAULT_CATEGORY:
            print(
                f"CANH BAO: San pham '{name}' se giu danh muc mac dinh "
                f"(khong tim thay danh muc khop: '{category_name}')."
            )

        products.append({
            "excel_row": row_num,
            "name": name,
            "slug": slug,
            "category_name": category_name,
            "category_value": category_value,
            "description": text_or_space(get_value("description")),
            "content": text_or_space(get_value("content")),
            "regular_price": price_to_text(
                get_value("regular_price")
            ),
            "sale_price": price_to_text(
                get_value("sale_price")
            ),
        })

    workbook.close()

    if MAX_PRODUCTS is not None:
        products = products[:MAX_PRODUCTS]

    return products


# =========================
# NHAT KY
# =========================

def write_report(rows):
    with open(
        REPORT_FILE,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "excel_row",
                "name",
                "slug",
                "status",
                "detail",
            ]
        )
        writer.writeheader()
        writer.writerows(rows)


def log_result(results, product, status, detail):
    result = {
        "excel_row": product["excel_row"],
        "name": product["name"],
        "slug": product["slug"],
        "status": status,
        "detail": detail,
    }
    results.append(result)

    print(f"KET QUA: {status}")
    print(f"CHI TIET: {detail}")

    # Cap nhat bao cao sau tung san pham
    write_report(results)


# =========================
# KIEM TRA FORM
# =========================

def form_is_ready(page):
    try:
        page.locator("#id_list").wait_for(
            state="visible",
            timeout=3000
        )
        page.locator("#namevi").wait_for(
            state="visible",
            timeout=3000
        )
        page.locator("#slugvi").wait_for(
            state="visible",
            timeout=3000
        )
        return True
    except PlaywrightTimeoutError:
        return False


def wait_for_add_form(page, add_form_url):
    # Thu dung lai trang form da duoc nguoi dung mo va xac nhan
    page.goto(add_form_url, wait_until="domcontentloaded")
    page.wait_for_timeout(1500)

    if form_is_ready(page):
        return True

    # Neu bi chuyen ve login, khong tu dong dien vao trang sai
    if "/admin/user/login" in page.url:
        return False

    try:
        page.reload(wait_until="domcontentloaded")
        page.wait_for_timeout(1500)
    except Exception:
        pass

    return form_is_ready(page)


def fill_text(page, selector, value):
    locator = page.locator(selector).first
    locator.wait_for(state="visible", timeout=10000)
    locator.fill(value)


def fill_content_editor(page, value):
    iframe_body = page.locator(
        'iframe[title*="contentvi"]'
    ).content_frame.locator("body")

    try:
        iframe_body.wait_for(state="visible", timeout=5000)
        iframe_body.fill(value)
        return
    except Exception:
        pass

    # Du phong neu trang khong dung iframe
    locator = page.locator("#contentvi").first
    locator.wait_for(state="visible", timeout=5000)
    locator.fill(value)


def fill_price(page, selector, value):
    locator = page.locator(selector).first
    locator.wait_for(state="visible", timeout=10000)

    # Gia trong Excel rong thi de trong, khong dien so 0
    locator.fill(value)


def fill_product_form(page, product):
    page.locator("#id_list").wait_for(
        state="visible",
        timeout=10000
    )

    page.locator("#id_list").select_option(
        value=product["category_value"]
    )

    selected_value = page.locator("#id_list").input_value()
    if selected_value != product["category_value"]:
        raise RuntimeError("Khong chon duoc danh muc cap 1")

    fill_text(page, "#namevi", product["name"])
    fill_text(page, "#slugvi", product["slug"])
    fill_text(page, "#descvi", product["description"])
    fill_content_editor(page, product["content"])

    fill_price(
        page,
        'input[name="data[regular_price]"]',
        product["regular_price"]
    )
    fill_price(
        page,
        'input[name="data[sale_price]"]',
        product["sale_price"]
    )


# =========================
# LUU VA PHAN LOAI KET QUA
# =========================

def get_page_text(page):
    try:
        return page.locator("body").inner_text(timeout=5000).lower()
    except Exception:
        return ""


def classify_result(page, old_url):
    """
    Chi xac nhan thanh cong neu URL/trang cho dau hieu da xu ly.
    Neu URL van la trang them san pham, kiem tra loi trung slug.
    """

    page.wait_for_timeout(WAIT_AFTER_SAVE_SECONDS)

    current_url = page.url
    body_text = get_page_text(page)

    duplicate_terms = [
        "slug đã tồn tại",
        "slug da ton tai",
        "đã tồn tại",
        "da ton tai",
        "bị trùng",
        "bi trung",
        "trùng slug",
        "trung slug",
        "duplicate",
        "already exists",
    ]

    error_terms = [
        "không được để trống",
        "khong duoc de trong",
        "vui lòng nhập",
        "vui long nhap",
        "lỗi",
        "loi",
        "error",
    ]

    # Dấu hiệu lỗi trùng slug
    if any(term in body_text for term in duplicate_terms):
        return (
            "BO QUA - TRUNG SLUG",
            "Website hien thi thong bao trung slug."
        )

    # Dấu hiệu trang xử lý lưu hoặc chuyển sang trang danh sách
    if "/admin/product/save/" in current_url:
        return (
            "CAN XAC MINH",
            "Da vao URL xu ly save; can kiem tra trang danh sach."
        )

    # Nếu form đã rời khỏi trang thêm và không phải trang đăng nhập
    if current_url != old_url and "/admin/user/login" not in current_url:
        if any(term in body_text for term in error_terms):
            return (
                "CAN XAC MINH",
                "URL da thay doi nhung van thay tu khoa loi."
            )
        return (
            "CAN XAC MINH",
            f"URL da thay doi sau khi luu: {current_url}"
        )

    # Nếu vẫn ở trang add, có thể lỗi validation hoặc trùng slug
    if "/admin/product/add/" in current_url:
        if any(term in body_text for term in error_terms):
            return (
                "LOI LUU",
                "Form van mo va co dau hieu loi. Kiem tra thong bao tren web."
            )

        return (
            "CHUA XAC MINH",
            "Van o trang them san pham; khong the khang dinh da luu."
        )

    return (
        "CHUA XAC MINH",
        f"Khong nhan dien duoc trang sau khi luu: {current_url}"
    )


def click_save(page):
    # Chi tim nut co ten chinh xac la Luu
    buttons = page.locator(
        "button, input[type='submit'], input[type='button']"
    )

    for index in range(buttons.count()):
        button = buttons.nth(index)

        try:
            if not button.is_visible() or not button.is_enabled():
                continue

            label = (
                button.inner_text(timeout=500).strip()
                if button.evaluate("(el) => el.tagName.toLowerCase() !== 'input'")
                else (button.get_attribute("value") or "").strip()
            )

            if label.lower() == "lưu" or label.lower() == "luu":
                button.click(timeout=5000)
                return True
        except Exception:
            continue

    return False


# =========================
# CHAY CHUONG TRINH
# =========================

def main():
    products = read_products()

    if not products:
        print("Khong co san pham nao trong Excel.")
        return

    print(f"Tong san pham se xu ly: {len(products)}")
    print(f"File Excel: {EXCEL_FILE}")
    print(f"Bao cao: {REPORT_FILE}")

    results = []

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            viewport={"width": 1440, "height": 950}
        )

        page = context.pages[0] if context.pages else context.new_page()
        page.goto(LOGIN_URL, wait_until="domcontentloaded")

        print("\nBUOC CHUAN BI:")
        print("1. Dang nhap admin neu duoc yeu cau.")
        print("2. Mo trang THEM SAN PHAM.")
        print("3. Cho form them san pham hien ra.")
        input("\nKhi form da hien day du, nhan Enter de bat dau tu dong...")

        # Khong chap nhan URL login lam URL form
        if not form_is_ready(page):
            print("\nLOI: Trang hien tai khong phai form them san pham.")
            print("Hay mo dung trang THEM SAN PHAM roi chay lai.")
            context.close()
            return

        add_form_url = page.url
        print(f"\nDa xac nhan form them san pham: {add_form_url}")

        for index, product in enumerate(products, start=1):
            print("\n" + "=" * 60)
            print(f"SAN PHAM {index}/{len(products)}")
            print(f"DONG EXCEL: {product['excel_row']}")
            print(f"TEN: {product['name']}")
            print(f"SLUG: {product['slug']}")
            print("=" * 60)

            try:
                if not wait_for_add_form(page, add_form_url):
                    log_result(
                        results,
                        product,
                        "DUNG - MAT FORM / CHUA DANG NHAP",
                        "Khong tim thay form them san pham. Dung de tranh thao tac sai."
                    )
                    print("Chuong trinh dung an toan.")
                    break

                fill_product_form(page, product)

                old_url = page.url
                if not click_save(page):
                    log_result(
                        results,
                        product,
                        "LOI LUU",
                        "Khong tim thay nut Luu hien thi."
                    )
                    continue

                print("Da nhan nut Luu, dang doi ket qua...")
                status, detail = classify_result(page, old_url)

                log_result(results, product, status, detail)

                if status == "CHUA XAC MINH":
                    print(
                        "Khong the xac nhan trang thai. "
                        "Dung de tranh tao trung hoac bo sot."
                    )
                    break

                # Chuyen sang san pham tiep theo neu co the mo lai form
                if index < len(products):
                    page.wait_for_timeout(1000)

            except Exception as error:
                log_result(
                    results,
                    product,
                    "LOI",
                    str(error)
                )

                print(
                    "Da ghi nhan loi. Thu mo lai form cho san pham tiep theo..."
                )

                try:
                    if not wait_for_add_form(page, add_form_url):
                        print(
                            "Khong mo lai duoc form. Dung chuong trinh an toan."
                        )
                        break
                except Exception:
                    print("Khong the khoi phuc form. Dung chuong trinh.")
                    break

        print("\n" + "=" * 60)
        print("DA KET THUC LUOT CHAY")
        print(f"Bao cao: {REPORT_FILE}")

        for status in sorted(set(row["status"] for row in results)):
            count = sum(1 for row in results if row["status"] == status)
            print(f"{status}: {count}")

        print("\nKiem tra file import_report.csv truoc khi chay lai.")
        input("Nhan Enter de dong trinh duyet...")
        context.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nDa dung theo yeu cau.")
    except Exception as error:
        print(f"\nLOI CHUONG TRINH: {error}")
