
from pathlib import Path
import re
import unicodedata

from playwright.sync_api import sync_playwright

# ==========================================
# 1. CẤU HÌNH ADMIN
# ==========================================

ADMIN_URL = (
    "https://demo44.nasanivietnam.net/2026/thang10/"
    "beauutypharma_1783126w/admin/user/login"
)

PROFILE_DIR = str(
    Path.home() / "auto-import-products" / "browser_profile"
)

# ==========================================
# 2. THÔNG TIN SẢN PHẨM THỬ
# ==========================================

PRODUCT = {
    "title": "SAN PHAM THU PLAYWRIGHT - XOA SAU KHI TEST",
    "description": (
        "San pham thu nghiem tu dong hoa. "
        "Vui long xoa sau khi test."
    ),
    "content": (
        "Noi dung thu nghiem Playwright. "
        "Khong phai san pham ban that."
    ),
    "regular_price": "100000",
    "sale_price": "90000",
}

# Danh mục cấp 1: CHĂM SÓC DA
CATEGORY_LEVEL_1 = "1"


# ==========================================
# 3. TẠO SLUG
# ==========================================

def make_slug(text):
    text = text.lower().replace("đ", "d")
    text = unicodedata.normalize("NFD", text)
    text = "".join(
        c for c in text
        if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


# ==========================================
# 4. HÀM ĐỌC CHỮ TRÊN NÚT
# ==========================================

def get_button_text(btn):
    tag = btn.evaluate("(el) => el.tagName").lower()

    if tag == "input":
        return (btn.get_attribute("value") or "").strip()

    return btn.inner_text().strip()


# ==========================================
# 5. CHẠY PLAYWRIGHT
# ==========================================

with sync_playwright() as p:

    context = p.chromium.launch_persistent_context(
        user_data_dir=PROFILE_DIR,
        headless=False,
    )

    page = (
        context.pages[0]
        if context.pages
        else context.new_page()
    )

    try:
        # Mở trang đăng nhập admin
        page.goto(
            ADMIN_URL,
            wait_until="domcontentloaded",
            timeout=60000,
        )

        print("\nĐã mở trang admin:", page.url)
        print("Đăng nhập nếu cần.")
        print("Tự mở trang THÊM SẢN PHẨM.")

        input(
            "\nKhi form Thêm sản phẩm đã mở, "
            "nhấn Enter tại Terminal..."
        )

        # Kiểm tra các trường
        required_fields = [
            "#namevi",
            "#slugvi",
            "#descvi",
            'input[name="data[regular_price]"]',
            'input[name="data[sale_price]"]',
            "#id_list",
        ]

        for selector in required_fields:
            page.locator(selector).first.wait_for(
                state="visible",
                timeout=20000,
            )

        # ==========================================
        # 6. CHỌN DANH MỤC CẤP 1
        # ==========================================

        category = page.locator("#id_list")

        category.select_option(
            value=CATEGORY_LEVEL_1
        )

        selected_category = category.locator(
            "option:checked"
        ).inner_text().strip()

        if selected_category != "CHĂM SÓC DA":
            raise RuntimeError(
                "Danh mục không đúng: "
                + selected_category
                + ". Đã dừng, chưa lưu."
            )

        # ==========================================
        # 7. ĐIỀN THÔNG TIN SẢN PHẨM
        # ==========================================

        page.locator("#namevi").fill(
            PRODUCT["title"]
        )

        page.locator("#slugvi").fill(
            make_slug(PRODUCT["title"])
        )

        page.locator("#descvi").fill(
            PRODUCT["description"]
        )

        page.locator(
            'input[name="data[regular_price]"]'
        ).fill(PRODUCT["regular_price"])

        page.locator(
            'input[name="data[sale_price]"]'
        ).fill(PRODUCT["sale_price"])

        # Điền nội dung vào CKEditor
        editor = page.frame_locator(
            'iframe[title*="contentvi"]'
        )

        editor.locator("body").fill(
            PRODUCT["content"]
        )

        # ==========================================
        # 8. HIỂN THỊ THÔNG TIN ĐỂ KIỂM TRA
        # ==========================================

        print("\n========== THÔNG TIN SẢN PHẨM ==========")
        print("Tiêu đề:", PRODUCT["title"])
        print("Slug:", make_slug(PRODUCT["title"]))
        print("Danh mục cấp 1:", selected_category)
        print("Giá gốc:", PRODUCT["regular_price"])
        print("Giá khuyến mãi:", PRODUCT["sale_price"])
        print("Danh mục cấp 2 và cấp 3: không tự chọn")

        print("\nHãy kiểm tra dữ liệu trên trình duyệt.")

        # Xác nhận lần thứ nhất
        confirm = input(
            '\nMuốn lưu sản phẩm thử, gõ LUU: '
        ).strip()

        if confirm != "LUU":
            print("Đã hủy. Không lưu sản phẩm.")
            input("Nhấn Enter để đóng trình duyệt...")
            raise SystemExit

        # ==========================================
        # 9. TÌM NÚT LƯU
        # ==========================================

        candidates = page.locator(
            'button[name="button-out"], '
            'input[name="button-out"], '
            'button[type="submit"], '
            'input[type="submit"]'
        )

        matched_buttons = []

        for i in range(candidates.count()):
            btn = candidates.nth(i)

            if not btn.is_visible() or not btn.is_enabled():
                continue

            if get_button_text(btn) == "Lưu":
                matched_buttons.append(btn)

        if not matched_buttons:
            print("\nKhông tìm thấy nút Lưu.")
            print("Đã dừng, chưa nhấn nút.")
            input("Nhấn Enter để kết thúc...")
            raise SystemExit

        # Chọn nút Lưu đầu tiên đang hiển thị
        save_button = matched_buttons[0]

        print(
            f"\nTìm thấy {len(matched_buttons)} nút Lưu."
        )
        print("Sẽ dùng nút Lưu đầu tiên đang hiển thị.")

        # Xác nhận lần thứ hai
        final_confirm = input(
            '\nXác nhận nhấn Lưu, gõ LUU: '
        ).strip()

        if final_confirm != "LUU":
            print("Đã hủy. Không nhấn nút Lưu.")
            input("Nhấn Enter để kết thúc...")
            raise SystemExit

        # ==========================================
        # 10. NHẤN LƯU MỘT LẦN
        # ==========================================

        original_url = page.url

        print("\nĐang nhấn nút Lưu...")

        save_button.click(timeout=10000)

        # ==========================================
        # 11. THEO DÕI CHUYỂN TRANG
        # ==========================================

        try:
            page.wait_for_url(
                lambda url: str(url) != original_url,
                timeout=10000,
            )

            print("\nURL sau khi nhấn Lưu:", page.url)

        except Exception:
            print("\nURL chưa thay đổi trong 10 giây.")
            print("Không tự nhấn Lưu lần nữa.")

        print(
            "\nHãy kiểm tra thông báo thành công "
            "và danh sách sản phẩm trên admin."
        )

        input(
            "Kiểm tra xong, nhấn Enter để đóng trình duyệt..."
        )

    except SystemExit:
        pass

    except Exception as error:
        print("\nĐÃ XẢY RA LỖI:")
        print(repr(error))
        print(
            "Không tự nhấn Lưu lại. "
            "Hãy kiểm tra trạng thái trên trình duyệt."
        )
        input("Nhấn Enter để kết thúc...")

    finally:
        context.close()
