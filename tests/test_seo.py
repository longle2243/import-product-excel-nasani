import csv
import contextlib
import importlib
import io
import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

import user_config
from nasani import seo_data, seo_detector
from nasani.browser_manager import validate_profile
from nasani.config import load_seo_data, load_site_config
from nasani.main import main as menu_main
from nasani.report_manager import save_report
from nasani.seo_report import save_report as save_json_report
from nasani.seo_scanner import safe_url
from nasani.seo_updater import (
    _select_update_records,
    _validate_record_url,
    discover_modules,
    extract_editable_rows,
    scan_module,
    scan_website,
)
from nasani.seo_report import update_summary


class SeoToolsTests(unittest.TestCase):
    def test_user_config_provides_website_and_legacy_seo_data(self):
        site = load_site_config()
        configured_data = load_seo_data()

        self.assertEqual(site["website_url"], user_config.WEBSITE_URL)
        self.assertTrue(site["admin_url"].startswith(site["website_url"]))
        self.assertEqual(set(configured_data), {
            "seo_title",
            "seo_keywords",
            "seo_description",
            "primary_keyword",
        })
        self.assertIs(seo_data.SEO_DATA, user_config.SEO_DATA)

    def test_user_config_rejects_invalid_urls_and_seo_values(self):
        with patch.object(user_config, "WEBSITE_URL", "http://insecure.example"):
            with self.assertRaisesRegex(ValueError, "WEBSITE_URL"):
                load_site_config()

        with patch.object(user_config, "SEO_DATA", {"seo_title": ""}):
            with self.assertRaisesRegex(ValueError, "SEO_DATA"):
                load_seo_data()

    def test_user_config_uses_explicit_admin_and_login_urls(self):
        with (
            patch.object(user_config, "WEBSITE_URL", "https://nasani.example"),
            patch.object(
                user_config,
                "ADMIN_URL",
                "https://nasani.example/control-panel",
            ),
            patch.object(
                user_config,
                "LOGIN_URL",
                "https://nasani.example/sign-in",
            ),
        ):
            site = load_site_config()
        self.assertEqual(site["admin_url"], "https://nasani.example/control-panel")
        self.assertEqual(site["login_url"], "https://nasani.example/sign-in")

    def test_urls_use_the_configured_website_not_a_fixed_domain(self):
        with patch.object(
            user_config,
            "WEBSITE_URL",
            "https://shop.example.net/deployment",
        ):
            site = load_site_config()
            record_url = (
                site["admin_url"] + "/unfamiliar-module/edit/42"
            )
            self.assertEqual(
                safe_url(site["admin_url"], record_url),
                record_url,
            )
            self.assertEqual(_validate_record_url(record_url), record_url)
            self.assertIsNone(
                safe_url(
                    site["admin_url"],
                    "https://2tskinbar.com/admin/unfamiliar-module/edit/42",
                )
            )

    def test_discovery_only_accepts_menu_urls_on_configured_admin(self):
        with patch.object(
            user_config,
            "WEBSITE_URL",
            "https://nasani.example/deployment",
        ):
            site = load_site_config()

            class Locator:
                def __init__(self, values=None):
                    self.values = values or []

                def count(self):
                    return 0

                def evaluate_all(self, _script):
                    return self.values

            class FakePage:
                url = site["admin_url"]

                def locator(self, selector):
                    if "nav a[href]" in selector:
                        return Locator([
                            {
                                "url": site["admin_url"] + "/unfamiliar/list",
                                "text": "Danh mục",
                            },
                            {
                                "url": "https://outside.example/deployment/admin/module",
                                "text": "Ngoài website",
                            },
                            {
                                "url": "https://nasani.example/other/admin/module",
                                "text": "Ngoài khu vực quản trị",
                            },
                        ])
                    return Locator()

                def goto(self, url, **_kwargs):
                    self.url = url
                    return None

            modules = discover_modules(FakePage())
            self.assertEqual(
                modules,
                [{
                    "name": "Danh mục",
                    "url": site["admin_url"] + "/unfamiliar/list",
                }],
            )

    def test_editable_rows_require_configured_admin_urls(self):
        with patch.object(
            user_config,
            "WEBSITE_URL",
            "https://nasani.example/deployment",
        ):
            site = load_site_config()

            class Locator:
                def evaluate_all(self, _script):
                    return [{
                        "title": "Bản ghi",
                        "edit_urls": [
                            site["admin_url"] + "/unfamiliar/edit/42",
                            "https://outside.example/deployment/admin/module/edit/8",
                            "https://nasani.example/other/admin/module/edit/9",
                        ],
                    }]

            class FakePage:
                def locator(self, _selector):
                    return Locator()

            self.assertEqual(
                extract_editable_rows(FakePage()),
                {site["admin_url"] + "/unfamiliar/edit/42": "Bản ghi"},
            )

    def test_scan_is_read_only_and_reports_configured_website(self):
        with patch.object(
            user_config,
            "WEBSITE_URL",
            "https://nasani.example/deployment",
        ):
            site = load_site_config()

            class FakePage:
                url = site["admin_url"] + "/unfamiliar/list"

                def locator(self, _selector):
                    class ReadOnlyLocator:
                        def fill(self, *_args, **_kwargs):
                            raise AssertionError("SCAN must not fill fields")

                        def click(self, *_args, **_kwargs):
                            raise AssertionError("SCAN must not click controls")

                    return ReadOnlyLocator()

            with (
                patch(
                    "nasani.seo_updater.navigate_page",
                    side_effect=lambda page, url: setattr(page, "url", url),
                ),
                patch("nasani.seo_updater.count_table_rows", return_value=0),
                patch("nasani.seo_updater.extract_editable_rows", return_value={}),
                patch("nasani.seo_updater.pagination_urls", return_value=[]),
                patch(
                    "nasani.seo_updater.detect_seo_fields",
                    return_value=({}, []),
                ),
            ):
                module_report, records = scan_module(
                    FakePage(),
                    {
                        "name": "Danh mục",
                        "url": site["admin_url"] + "/unfamiliar/list",
                    },
                )
            self.assertEqual(module_report["records_opened"], 0)
            self.assertEqual(records, [])

            with (
                patch(
                    "nasani.seo_updater.discover_modules",
                    return_value=[{
                        "name": "Danh mục",
                        "url": site["admin_url"] + "/unfamiliar/list",
                    }],
                ),
                patch(
                    "nasani.seo_updater.scan_module",
                    return_value=(module_report, records),
                ),
                patch("nasani.seo_updater.save_report"),
            ):
                report = scan_website(FakePage())
            self.assertEqual(report["mode"], "SCAN")
            self.assertEqual(report["website"], site["website_url"])

    def test_excel_menu_still_dispatches_to_existing_import_module(self):
        importlib.import_module("nasani.import_excel")
        with (
            patch("nasani.main.run_python", return_value=True) as run_python,
            patch("builtins.input", side_effect=["1", "0"]),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            menu_main()
        run_python.assert_called_once_with("-m", "nasani.import_excel")

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
