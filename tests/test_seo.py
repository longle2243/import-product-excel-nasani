import csv
import json
import tempfile
import unittest
from pathlib import Path

from nasani import seo_detector
from nasani.browser_manager import validate_profile
from nasani.report_manager import save_report
from nasani.seo_report import save_report as save_json_report
from nasani.seo_scanner import safe_url
from nasani.seo_updater import _select_update_records, _validate_record_url
from nasani.seo_report import update_summary


class SeoToolsTests(unittest.TestCase):
    def test_scanner_accepts_only_safe_admin_urls(self):
        base = "https://2tskinbar.com/admin"
        self.assertEqual(
            safe_url(base, "/admin/product/?action=edit"),
            "https://2tskinbar.com/admin/product/?action=edit",
        )
        self.assertIsNone(safe_url(base, "https://example.com/admin"))
        self.assertIsNone(safe_url(base, "/admin/product/delete/1"))
        self.assertIsNone(safe_url(base, "/admin/user/logout"))
        self.assertIsNone(
            safe_url(base, "/admin/product/?action=delete&id=1")
        )

    def test_update_selects_only_the_explicit_record(self):
        records = [
            {"edit_url": "https://2tskinbar.com/admin/product/edit/1", "seo_fields": {"seo_title": []}},
            {"edit_url": "https://2tskinbar.com/admin/seopage/man/trang-chu", "seo_fields": {"seo_title": []}},
        ]
        target = records[1]["edit_url"]
        self.assertEqual(
            _select_update_records(records, record_url=target, limit=1),
            [records[1]],
        )
        self.assertEqual(_select_update_records(records), records)
        self.assertEqual(_select_update_records(records, limit=1), records[:1])
        with self.assertRaises(RuntimeError):
            _select_update_records(records, record_url=target + "/missing", limit=1)
        with self.assertRaises(ValueError):
            _validate_record_url("https://example.com/admin/seopage/man/trang-chu")

    def test_profile_validation_does_not_create_directories(self):
        with tempfile.TemporaryDirectory() as temporary:
            missing = Path(temporary) / "missing-profile"
            with self.assertRaises(RuntimeError):
                validate_profile(missing)
            self.assertFalse(missing.exists())

            empty = Path(temporary) / "empty-profile"
            empty.mkdir()
            with self.assertRaises(RuntimeError):
                validate_profile(empty)

            (empty / "Preferences").write_text("{}", encoding="utf-8")
            self.assertEqual(validate_profile(empty), empty.resolve())

    def test_detector_adapts_identified_and_uncertain_fields(self):
        class FakePage:
            url = "https://2tskinbar.com/admin/product/edit/1"

            def locator(self, _selector):
                return FakeLocator()

        class FakeLocator:
            def evaluate_all(self, _script):
                return [
                    {
                        "tag": "input",
                        "type": "text",
                        "name": "seo_title",
                        "id": "",
                        "placeholder": "",
                        "aria_label": "",
                        "labels": [],
                        "value": "Title",
                        "visible": True,
                        "disabled": False,
                        "editable": True,
                    },
                    {
                        "tag": "textarea",
                        "type": "",
                        "name": "meta_custom",
                        "id": "",
                        "placeholder": "",
                        "aria_label": "",
                        "labels": [],
                        "value": "Value",
                        "visible": True,
                        "disabled": False,
                        "editable": True,
                    },
                ]

        fields = seo_detector.detect(FakePage())

        self.assertEqual(fields[0]["status"], "identified")
        self.assertEqual(fields[0]["key"], "seo_title")
        self.assertEqual(fields[1]["status"], "unrecognized")
        self.assertEqual(fields[1]["value"], "Value")
        self.assertEqual(seo_detector.normalize("Tiêu đề SEO"), "tieu de seo")

    def test_report_saves_json_and_csv(self):
        report = {
            "pages": [{
                "url": "https://2tskinbar.com/admin/product/edit/1",
                "module": "Products",
                "record": "Product 1",
                "title": "Product 1",
                "status": "scanned",
                "fields": [{
                    "key": "seo_title",
                    "status": "identified",
                    "value": "Title",
                }],
            }]
        }
        with tempfile.TemporaryDirectory() as temporary:
            save_report(temporary, report)
            json_path = Path(temporary) / "scan_report.json"
            csv_path = Path(temporary) / "scan_report.csv"
            self.assertEqual(
                json.loads(json_path.read_text(encoding="utf-8")),
                report,
            )
            with csv_path.open(encoding="utf-8-sig", newline="") as source:
                row = next(csv.DictReader(source))
            self.assertEqual(row["field"], "seo_title")
            self.assertEqual(row["value"], "Title")

    def test_report_summary_handles_missing_and_string_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            json_path = Path(temporary) / "summary.json"
            report = {"records": None, "modules": None}
            update_summary(report)
            self.assertEqual(report["summary"]["total_modules"], 0)
            self.assertEqual(report["summary"]["total_records"], 0)

            save_json_report({"status": "ok"}, str(json_path))
            self.assertEqual(json.loads(json_path.read_text(encoding="utf-8"))["status"], "ok")


if __name__ == "__main__":
    unittest.main()
