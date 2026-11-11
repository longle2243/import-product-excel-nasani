"""Load and validate settings from the user-editable root configuration."""

from urllib.parse import urlsplit, urlunsplit


SEO_KEYS = {
    "seo_title",
    "seo_keywords",
    "seo_description",
    "primary_keyword",
}


def _normalized_https_url(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("{} phải là URL HTTPS hợp lệ.".format(label))

    try:
        parsed = urlsplit(value.strip())
        port = parsed.port
    except ValueError as error:
        raise ValueError("{} không phải URL hợp lệ.".format(label)) from error
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "{} phải bắt đầu bằng https:// và không có thông tin đăng nhập, "
            "query hoặc fragment.".format(label)
        )
    hostname = parsed.hostname.lower()
    netloc = "[{}]".format(hostname) if ":" in hostname else hostname
    if port is not None:
        netloc = "{}:{}".format(netloc, port)
    path = parsed.path.rstrip("/")
    return urlunsplit(("https", netloc, path, "", ""))


def _origin(url):
    parsed = urlsplit(url)
    port = parsed.port or 443
    return parsed.scheme.lower(), parsed.hostname.lower(), port


def load_site_config():
    try:
        import user_config
    except ModuleNotFoundError as error:
        if error.name != "user_config":
            raise
        raise RuntimeError(
            "Không tìm thấy user_config.py ở thư mục gốc dự án."
        ) from error

    website_url = _normalized_https_url(
        getattr(user_config, "WEBSITE_URL", None),
        "WEBSITE_URL",
    )
    configured_admin_url = getattr(user_config, "ADMIN_URL", "")
    if not isinstance(configured_admin_url, str):
        raise ValueError("ADMIN_URL phải là chuỗi hoặc để trống.")
    admin_url = (
        _normalized_https_url(configured_admin_url.strip(), "ADMIN_URL")
        if configured_admin_url.strip()
        else website_url + "/admin"
    )
    if _origin(website_url) != _origin(admin_url):
        raise ValueError("ADMIN_URL phải thuộc cùng website với WEBSITE_URL.")
    if not urlsplit(admin_url).path:
        raise ValueError("ADMIN_URL phải trỏ đến đường dẫn quản trị.")

    configured_login_url = getattr(user_config, "LOGIN_URL", "")
    if not isinstance(configured_login_url, str):
        raise ValueError("LOGIN_URL phải là chuỗi hoặc để trống.")
    login_url = (
        _normalized_https_url(configured_login_url.strip(), "LOGIN_URL")
        if configured_login_url.strip()
        else ""
    )
    if login_url and _origin(website_url) != _origin(login_url):
        raise ValueError("LOGIN_URL phải thuộc cùng website với WEBSITE_URL.")

    admin_path = urlsplit(admin_url).path.rstrip("/") or "/"
    if admin_path == "/":
        raise ValueError("ADMIN_URL không được là trang gốc website.")

    return {
        "website_url": website_url,
        "admin_url": admin_url,
        "login_url": login_url,
    }


def load_seo_data():
    try:
        import user_config
    except ModuleNotFoundError as error:
        if error.name != "user_config":
            raise
        raise RuntimeError(
            "Không tìm thấy user_config.py ở thư mục gốc dự án."
        ) from error

    data = getattr(user_config, "SEO_DATA", None)
    if not isinstance(data, dict):
        raise ValueError("SEO_DATA phải là một dictionary trong user_config.py.")
    if set(data) != SEO_KEYS:
        raise ValueError(
            "SEO_DATA cần đúng 4 khóa: " + ", ".join(sorted(SEO_KEYS))
        )
    for key in sorted(SEO_KEYS):
        if not isinstance(data[key], str) or not data[key].strip():
            raise ValueError(
                "SEO_DATA['{}'] phải là chuỗi không được để trống.".format(key)
            )
    return data


def is_within_admin_url(url, admin_url):
    try:
        target = urlsplit(url)
        admin = urlsplit(admin_url)
        target_origin = _origin(url)
        admin_origin = _origin(admin_url)
    except (AttributeError, TypeError, ValueError):
        return False
    if target.scheme.lower() != "https" or target_origin != admin_origin:
        return False

    admin_path = admin.path.rstrip("/") or "/"
    return (
        target.path.rstrip("/") == admin_path
        or target.path.startswith(admin_path.rstrip("/") + "/")
    )
