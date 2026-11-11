import json
import os


def save_report(report, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")

    with temporary_path.open("w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)
        file.write("\n")

    os.replace(str(temporary_path), str(path))


def update_summary(report):
    records = report.get("records", [])
    modules = report.get("modules", [])
    report["summary"] = {
        "total_modules": len(modules),
        "accessible_modules": sum(
            1 for module in modules if module.get("accessible")
        ),
        "total_records": sum(
            module.get("record_count", 0) for module in modules
        ),
        "records_opened_for_inspection": sum(
            module.get("records_opened", 0) for module in modules
        ),
        "records_with_seo_fields": sum(
            1 for record in records if record.get("seo_fields")
        ),
        "updated_successfully": sum(
            1 for record in records
            if record.get("update_status") == "UPDATED_VERIFIED"
        ),
        "already_current": sum(
            1 for record in records
            if record.get("update_status") == "ALREADY_CURRENT"
        ),
        "failed_records": sum(
            1 for record in records
            if (record.get("update_status") or "").startswith("FAILED")
        ),
        "unrecognized_seo_fields": sum(
            len(record.get("unrecognized_fields", []))
            for record in records
        ),
        "unprocessed_records": sum(
            1 for record in records
            if record.get("scan_status") not in ("SCANNED", "NO_SEO_FIELDS")
        ) + sum(module.get("unprocessed_record_count", 0) for module in modules),
    }
