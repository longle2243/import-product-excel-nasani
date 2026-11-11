import argparse
import logging
from pathlib import Path
from browser_manager import PROFILE_DIR, validate_profile, open_browser, wait_for_login


def main():
    parser = argparse.ArgumentParser(description='NASANI SEO — read-only SCAN. UPDATE not enabled until live scan review.')
    parser.add_argument('--profile', type=Path, default=PROFILE_DIR)
    parser.add_argument('--reports', type=Path, default=Path(__file__).resolve().parent / 'reports')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--max-pages', type=int, default=1000)
    args = parser.parse_args()
    if args.max_pages < 1:
        parser.error('--max-pages must be positive')
    print('NASANI SEO AUTOMATION\n1. SCAN (mặc định)\n2. UPDATE (chưa mở: cần scan và kiểm chứng DOM)\n3. EXIT')
    choice = input('Chọn chế độ [1]: ').strip() or '1'
    if choice == '3':
        return
    if choice != '1':
        print('Không cập nhật. UPDATE chưa triển khai trước khi kiểm chứng SCAN thực tế.')
        return
    profile = validate_profile(args.profile)
    from playwright.sync_api import sync_playwright
    from seo_scanner import scan
    log_dir = Path(__file__).resolve().parent / 'logs'
    log_dir.mkdir(exist_ok=True)
    logging.basicConfig(filename=log_dir / 'scan.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    with sync_playwright() as playwright:
        context = open_browser(playwright, profile)
        try:
            page = context.pages[0] if context.pages else context.new_page()
            wait_for_login(page)
            report = scan(page, args.reports, args.max_pages, args.resume)
            print(report['summary'])
            print('Phạm vi: PARTIAL. Xem limitations, excluded_links và blocked_requests trong báo cáo.')
            input('Nhấn Enter khi muốn đóng trình duyệt: ')
        finally:
            context.close()


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, KeyboardInterrupt) as error:
        print(f'Dừng an toàn: {error}')
