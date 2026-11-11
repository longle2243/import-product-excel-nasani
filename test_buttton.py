
from pathlib import Path
from playwright.sync_api import sync_playwright

ADMIN_URL = "https://demo44.nasanivietnam.net/2026/thang10/beauutypharma_1783126w/admin/user/login"
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
                "\nDang nhap admin, tu tay mo trang THEM SAN PHAM, "
                "sau do quay lai Terminal va nhan Enter..."
            )

            print("\n=== THONG TIN TRANG ===")
            print("URL:", page.url)
            print("Title:", page.title())

            print("\n=== CAC SELECT DANG HIEN ===")
            selects = page.locator("select:visible")

            for i in range(selects.count()):
                s = selects.nth(i)
                print("SELECT", i + 1, s.evaluate("""el => ({
                    id: el.id,
                    name: el.name,
                    options: Array.from(el.options).map(o => ({
                        text: o.textContent.trim(),
                        value: o.value
                    }))
                })"""))

            print("\n=== CAC NUT DANG HIEN ===")
            buttons = page.locator(
                "button:visible, input[type=submit]:visible, "
                "input[type=button]:visible, a.btn:visible"
            )

            for i in range(buttons.count()):
                b = buttons.nth(i)
                try:
                    info = b.evaluate("""el => ({
                        tag: el.tagName,
                        text: (el.innerText || el.value || '').trim(),
                        type: el.getAttribute('type'),
                        id: el.id,
                        name: el.getAttribute('name')
                    })""")
                    print("BUTTON", i + 1, info)
                except Exception:
                    pass

            print("\n=== TRINH SOAN THAO ===")
            print("IFRAME count:", page.locator("iframe").count())

            for i in range(page.locator("iframe").count()):
                frame = page.locator("iframe").nth(i)
                print("IFRAME", i + 1, frame.evaluate("""el => ({
                    id: el.id,
                    title: el.title,
                    className: el.className
                })"""))

            print("\n=== HOAN TAT: CHUA SUA HAY LUU DU LIEU ===")
            input("Nhan Enter de dong trinh duyet...")

        finally:
            context.close()


if __name__ == "__main__":
    main()
