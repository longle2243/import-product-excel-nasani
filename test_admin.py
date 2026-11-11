
from pathlib import Path
from playwright.sync_api import sync_playwright

# Thay URL bằng địa chỉ trang admin của bạn
ADMIN_URL = "https://demo44.nasanivietnam.net/2026/thang10/beauutypharma_1783126w/admin"

PROFILE_DIR = Path.home() / "auto-import-products" / "browser_profile"


def main():
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            viewport={"width": 1440, "height": 900},
        )

        page = context.pages[0] if context.pages else context.new_page()

        try:
            page.goto(ADMIN_URL, wait_until="domcontentloaded")

            input(
                "\nDang nhap admin, mo trang Them san pham, "
                "sau do quay lai Terminal va nhan Enter..."
            )

            print("\nURL hien tai:", page.url)
            print("Tieu de trang:", page.title())

            fields = page.locator(
                "input, textarea, select, [contenteditable='true']"
            )

            print("\nSo truong tim thay:", fields.count())

            for i in range(fields.count()):
                try:
                    info = fields.nth(i).evaluate("""el => ({
                        tag: el.tagName,
                        type: el.getAttribute('type'),
                        name: el.getAttribute('name'),
                        id: el.id,
                        placeholder: el.getAttribute('placeholder')
                    })""")
                    print(f"{i + 1}. {info}")
                except Exception as error:
                    print(f"{i + 1}. Loi: {error}")

            input("\nNhan Enter de dong trinh duyet...")

        finally:
            context.close()


if __name__ == "__main__":
    main()
