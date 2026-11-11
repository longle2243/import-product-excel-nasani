"""JSON checkpoint and CSV export helpers for SEO scans."""
import csv
import os
from pathlib import Path

from seo_report import save_report as save_json_report


CSV_COLUMNS = (
    "url",
    "module",
    "record",
    "title",
    "field",
    "status",
    "value",
    "tag",
    "type",
    "name",
    "id",
    "placeholder",
    "selector",
    "confidence",
    "error",
)


def _csv_rows(report):
    for page in report.get("pages", []):
        fields = page.get("fields") or [{}]
        for field in fields:
            yield {
                "url": page.get("url", ""),
                "module": page.get("module", ""),
                "record": page.get("record", ""),
                "title": page.get("title", ""),
                "field": field.get("key", ""),
                "status": field.get("status", page.get("status", "")),
                "value": field.get("value", ""),
                "tag": field.get("tag", ""),
                "type": field.get("type", ""),
                "name": field.get("name", ""),
                "id": field.get("id", ""),
                "placeholder": field.get("placeholder", ""),
                "selector": field.get("selector", ""),
                "confidence": field.get("confidence", ""),
                "error": page.get("error", ""),
            }


def save_report(folder, report):
    folder = Path(folder)
    json_path = folder / "scan_report.json"
    csv_path = folder / "scan_report.csv"
    save_json_report(report, json_path)

    temporary_path = csv_path.with_suffix(csv_path.suffix + ".tmp")
    with temporary_path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(_csv_rows(report))
    os.replace(str(temporary_path), str(csv_path))
