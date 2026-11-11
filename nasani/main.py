import subprocess
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent.parent


def run_python(*args):
    command = [sys.executable, *args]
    print("\nChạy:", " ".join(command), flush=True)
    result = subprocess.run(command, cwd=PROJECT_DIR, check=False)
    if result.returncode:
        print(f"\nLệnh kết thúc với mã lỗi {result.returncode}.")
    return result.returncode == 0


def run_web_checks():
    while True:
        print(
            "\n=== KIỂM TRA DỰ ÁN ===\n"
            "1. Chạy kiểm thử tự động (không mở website)\n"
            "2. Mở admin và kiểm tra form (chỉ đọc)\n"
            "3. Chạy cả kiểm thử tự động và kiểm tra form\n"
            "0. Quay lại"
        )
        choice = input("Chọn [0]: ").strip() or "0"

        if choice == "0":
            return
        if choice == "1":
            run_python("-m", "unittest", "discover", "-s", "tests", "-v")
        elif choice == "2":
            run_python("-m", "tools.check_admin_form")
        elif choice == "3":
            if run_python("-m", "unittest", "discover", "-s", "tests", "-v"):
                run_python("-m", "tools.check_admin_form")
        else:
            print("Lựa chọn không hợp lệ.")


def update_all_seo():
    print("\nĐang SCAN trước; bước này không ghi dữ liệu website.")
    if not run_python("-m", "nasani.seo_updater"):
        return

    answer = input(
        "\nHãy xem báo cáo SCAN. Nếu muốn tiếp tục cập nhật toàn bộ, "
        "nhập UPDATE: "
    ).strip()
    if answer != "UPDATE":
        print("Đã hủy. Không chạy bước cập nhật SEO.")
        return

    print(
        "\nCẢNH BÁO: bước tiếp theo sẽ ghi nội dung SEO lên mọi bản ghi "
        "có trường SEO được nhận diện."
    )
    run_python(
        "-m",
        "nasani.seo_updater",
        "--mode",
        "UPDATE",
        "--confirm-update",
        "--confirm-all",
    )


def main():
    while True:
        print(
            "\n=== NASANI: MENU CHÍNH ===\n"
            "1. Nhập sản phẩm từ Excel\n"
            "2. Cập nhật nội dung SEO cho toàn website\n"
            "3. Kiểm tra dự án / website\n"
            "0. Thoát"
        )
        choice = input("Chọn [0]: ").strip() or "0"

        if choice == "0":
            return
        if choice == "1":
            run_python("-m", "nasani.import_excel")
        elif choice == "2":
            print(
                "\nLuồng này sẽ chạy SCAN không ghi dữ liệu trước. "
                "Sau khi xem báo cáo, bạn có thể quyết định có chạy UPDATE."
            )
            print(
                "Lưu ý: dữ liệu trong nasani/seo_data.py hiện được dùng chung "
                "cho mọi bản ghi; chưa có nội dung riêng theo từng trang."
            )
            update_all_seo()
        elif choice == "3":
            run_web_checks()
        else:
            print("Lựa chọn không hợp lệ.")


if __name__ == "__main__":
    main()
