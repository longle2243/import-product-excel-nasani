"""Compatibility adapter exposing the scanner's field-detection interface."""
from urllib.parse import urlsplit

from seo_field_detector import detect_seo_fields, normalize_hint


def normalize(value):
    return normalize_hint(value)


def detect(page):
    is_seopage = "/seopage/" in urlsplit(page.url).path.lower()
    identified, unrecognized = detect_seo_fields(
        page,
        is_seopage=is_seopage,
    )
    fields = [
        dict(field, key=key, status="identified")
        for key, matches in identified.items()
        for field in matches
    ]
    fields.extend(
        dict(field, key="", status="unrecognized")
        for field in unrecognized
    )
    return fields
