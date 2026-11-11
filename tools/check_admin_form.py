from playwright.sync_api import sync_playwright

from nasani.browser_manager import PROFILE_DIR, open_browser


ADMIN_URL = (
    "https://demo44.nasanivietnam.net/2026/thang10/"
    "beauutypharma_1783126w/admin"
)


def main():
    with sync_playwright() as playwright:
        context = open_browser(playwright, PROFILE_DIR)
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(ADMIN_URL, wait_until="domcontentloaded")
            input(
                "\nĐăng nhập nếu cần, tự mở trang cần kiểm tra rồi nhấn Enter. "
                "Công cụ chỉ đọc, không lưu dữ liệu..."
            )

            print("\nURL:", page.url)
            print("Tiêu đề:", page.title())

            fields = page.locator(
                "input, textarea, select, [contenteditable='true']"
            ).evaluate_all(
                """elements => elements.map(el => ({
                    tag: el.tagName,
                    type: el.getAttribute('type'),
                    name: el.getAttribute('name'),
                    id: el.id,
                    placeholder: el.getAttribute('placeholder')
                }))"""
            )
            print(f"\n=== TRƯỜNG NHẬP ({len(fields)}) ===")
            for index, field in enumerate(fields, start=1):
                print(f"{index}. {field}")

            selects = page.locator("select:visible").evaluate_all(
                """elements => elements.map(el => ({
                    id: el.id,
                    name: el.name,
                    options: Array.from(el.options).map(option => ({
                        text: option.textContent.trim(),
                        value: option.value
                    }))
                }))"""
            )
            print(f"\n=== DANH MỤC ({len(selects)}) ===")
            for index, select in enumerate(selects, start=1):
                print(f"{index}. {select}")

            buttons = page.locator(
                "button:visible, input[type=submit]:visible, "
                "input[type=button]:visible, a.btn:visible"
            ).evaluate_all(
                """elements => elements.map(el => ({
                    tag: el.tagName,
                    text: (el.innerText || el.value || '').trim(),
                    type: el.getAttribute('type'),
                    id: el.id,
                    name: el.getAttribute('name')
                }))"""
            )
            print(f"\n=== NÚT ({len(buttons)}) ===")
            for index, button in enumerate(buttons, start=1):
                print(f"{index}. {button}")

            frames = page.locator("iframe").evaluate_all(
                """elements => elements.map(el => ({
                    id: el.id,
                    title: el.title,
                    className: el.className
                }))"""
            )
            print(f"\n=== IFRAME ({len(frames)}) ===")
            for index, frame in enumerate(frames, start=1):
                print(f"{index}. {frame}")

            input("\nHoàn tất kiểm tra. Nhấn Enter để đóng trình duyệt...")
        finally:
            context.close()


if __name__ == "__main__":
    main()
