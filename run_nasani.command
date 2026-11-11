#!/bin/bash

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR" || exit 1

pause_and_exit() {
    printf "\n%s\n" "$1"
    read -r -p "Nhấn Enter để đóng cửa sổ..."
    exit 1
}

if ! command -v python3 >/dev/null 2>&1; then
    pause_and_exit "Không tìm thấy Python 3. Hãy cài Python 3 rồi chạy lại."
fi

if [ ! -x ".venv/bin/python" ]; then
    echo "Đang tạo môi trường Python lần đầu..."
    python3 -m venv .venv || pause_and_exit "Không tạo được môi trường Python."
fi

PYTHON="$PROJECT_DIR/.venv/bin/python"

if ! "$PYTHON" -c "import openpyxl, playwright" >/dev/null 2>&1; then
    echo "Đang cài thư viện cần thiết lần đầu..."
    "$PYTHON" -m pip install -r requirements.txt || pause_and_exit "Cài thư viện thất bại."
fi

BROWSER_READY=$("$PYTHON" -c \
    "from pathlib import Path; from playwright.sync_api import sync_playwright; p=sync_playwright().start(); print(Path(p.chromium.executable_path).is_file()); p.stop()" \
    2>/dev/null)
if [ "$BROWSER_READY" != "True" ]; then
    echo "Đang cài Chromium lần đầu..."
    "$PYTHON" -m playwright install chromium || pause_and_exit "Cài Chromium thất bại."
fi

echo
echo "Mở menu NASANI. Chọn 1 để nhập Excel hoặc 2 để chạy luồng SEO."
"$PYTHON" main.py
STATUS=$?

echo
if [ "$STATUS" -ne 0 ]; then
    echo "NASANI kết thúc với mã lỗi $STATUS."
fi
read -r -p "Nhấn Enter để đóng cửa sổ..."
exit "$STATUS"
