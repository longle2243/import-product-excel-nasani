import re
import unicodedata


FIELD_SELECTORS = "input, textarea, select, [contenteditable='true']"
IGNORED_TYPES = {"hidden", "checkbox", "radio", "file", "submit", "button", "password"}


def normalize_hint(value):
    value = unicodedata.normalize("NFKD", str(value or "").lower())
    value = value.replace("đ", "d")
    value = "".join(
        character
        for character in value
        if not unicodedata.combining(character)
    )
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value)).strip()


def describe_fields(page):
    return page.locator(FIELD_SELECTORS).evaluate_all(
        """elements => elements.map((el, index) => {
            const labels = Array.from(el.labels || [])
                .map(label => (label.innerText || label.textContent || '').trim())
                .filter(Boolean);
            const visible = Boolean(
                el.getClientRects().length &&
                getComputedStyle(el).visibility !== 'hidden' &&
                getComputedStyle(el).display !== 'none'
            );
            return {
                index,
                tag: el.tagName.toLowerCase(),
                type: (el.getAttribute('type') || '').toLowerCase(),
                name: el.getAttribute('name') || '',
                id: el.id || '',
                placeholder: el.getAttribute('placeholder') || '',
                aria_label: el.getAttribute('aria-label') || '',
                labels,
                value: 'value' in el ? el.value : (el.innerText || el.textContent || ''),
                visible,
                disabled: Boolean(el.disabled),
                editable: !el.disabled && !el.readOnly
            };
        })"""
    )


def _field_hint(field):
    parts = [
        field.get("name"),
        field.get("id"),
        field.get("placeholder"),
        field.get("aria_label"),
    ]
    parts.extend(field.get("labels") or [])
    return normalize_hint(" ".join(part for part in parts if part))


def _match_field(field, is_seopage):
    hint = _field_hint(field)
    if (
        field.get("type") == "search"
        and any(term in hint for term in ("tim kiem", "search"))
    ):
        return None, None

    primary_patterns = (
        r"\bfocus keyword\b",
        r"\bprimary keyword\b",
        r"\bkeyword chinh\b",
        r"\btu khoa chinh\b",
        r"\bseo focus\b",
        r"\bseo focusvi\b",
    )
    if any(re.search(pattern, hint) for pattern in primary_patterns):
        return "primary_keyword", "explicit-label-or-attribute"

    title_patterns = (
        r"\bseo title\b",
        r"\bmeta title\b",
        r"\bdata seo title",
    )
    if any(re.search(pattern, hint) for pattern in title_patterns):
        return "seo_title", "explicit-label-or-attribute"

    keywords_patterns = (
        r"\bseo keywords?\b",
        r"\bmeta keywords?\b",
        r"\bdata seo keywords?",
    )
    if any(re.search(pattern, hint) for pattern in keywords_patterns):
        return "seo_keywords", "explicit-label-or-attribute"

    description_patterns = (
        r"\bseo description\b",
        r"\bmeta description\b",
        r"\bdata seo description",
    )
    if any(re.search(pattern, hint) for pattern in description_patterns):
        return "seo_description", "explicit-label-or-attribute"

    if is_seopage:
        if re.search(r"\b(title|titlevi)\b", hint):
            return "seo_title", "generic-page-field-label"
        if re.search(r"\b(keywords?|keywordsvi)\b", hint):
            return "seo_keywords", "generic-page-field-label"
        if re.search(r"\b(description|descriptionvi)\b", hint):
            return "seo_description", "generic-page-field-label"

    is_candidate = any(
        term in hint
        for term in (
            "seo",
            "meta",
            "focus",
            "primary",
            "keyword",
            "tu khoa",
        )
    )
    if is_candidate:
        return None, "unclassified-seo-related-field"

    return None, None


def _locator_selector(field):
    field_id = field.get("id") or ""
    if field_id:
        escaped = field_id.replace("\\", "\\\\").replace('"', '\\"')
        return '[id="{}"]'.format(escaped)

    field_name = field.get("name") or ""
    if field_name:
        escaped = field_name.replace("\\", "\\\\").replace('"', '\\"')
        return '[name="{}"]'.format(escaped)

    return ""


def detect_seo_fields(page, is_seopage=False):
    found = {}
    unrecognized = []

    for field in describe_fields(page):
        if (
            not field["visible"]
            or field["disabled"]
            or not field["editable"]
            or field["type"] in IGNORED_TYPES
        ):
            continue

        key, confidence = _match_field(field, is_seopage)
        if key:
            found.setdefault(key, []).append({
                "key": key,
                "tag": field["tag"],
                "type": field["type"],
                "name": field["name"],
                "id": field["id"],
                "placeholder": field["placeholder"],
                "labels": field["labels"],
                "value": field["value"],
                "selector": _locator_selector(field),
                "confidence": confidence,
            })
        elif confidence:
            unrecognized.append({
                "tag": field["tag"],
                "type": field["type"],
                "name": field["name"],
                "id": field["id"],
                "placeholder": field["placeholder"],
                "labels": field["labels"],
                "value": field["value"],
                "reason": confidence,
            })

    return found, unrecognized


def unique_field_locator(page, field):
    selector = field.get("selector") or ""
    if not selector:
        return None

    locator = page.locator(selector)
    if locator.count() != 1:
        return None

    if not locator.is_visible() or not locator.is_editable():
        return None
    return locator
