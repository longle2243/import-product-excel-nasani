"""Browser and existing-profile helpers for the read-only SEO CLI."""
from pathlib import Path
from urllib.parse import urlparse


BASE_DIR = Path(__file__).resolve().parent
PROFILE_DIR = BASE_DIR / "browser_profile"
LOGIN_URL = "https://2tskinbar.com/admin/user/login"
ADMIN_URL = "https://2tskinbar.com/admin"


def validate_profile(profile):
    profile = Path(profile).expanduser().resolve()
    if not profile.is_dir():
        raise RuntimeError(
            "Không tìm thấy browser profile tại {}. "
            "Không tự tạo profile mới.".format(profile)
        )
    if not any(profile.iterdir()):
        raise RuntimeError(
            "Browser profile tại {} đang trống. "
            "Không tự tạo profile mới.".format(profile)
        )
    return profile


def open_browser(playwright, profile):
    profile = validate_profile(profile)
    try:
        return playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile),
            headless=False,
            viewport={"width": 1440, "height": 950},
        )
    except Exception as error:
        raise RuntimeError(
            "Không mở được browser profile {}. Đóng Chromium/Chrome đang "
            "dùng profile đó rồi thử lại. Lỗi: {}".format(profile, error)
        ) from error


def wait_for_login(page):
    page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
    if page.locator("#layout-menu").count():
        page.goto(ADMIN_URL, wait_until="domcontentloaded", timeout=30000)
        return

    print(
        "\nHãy đăng nhập trực tiếp trong cửa sổ Chromium. "
        "Không nhập mật khẩu vào terminal hoặc source."
    )
    input("Nhấn Enter sau khi đăng nhập xong: ")
    if (
        urlparse(page.url).path.rstrip("/") == "/admin/user/login"
        or not page.locator("#layout-menu").count()
    ):
        raise RuntimeError(
            "Chưa xác nhận được phiên admin sau khi đăng nhập."
        )
    page.goto(ADMIN_URL, wait_until="domcontentloaded", timeout=30000)
