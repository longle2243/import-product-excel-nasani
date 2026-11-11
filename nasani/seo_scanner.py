"""Conservative admin crawler. Reads actual hrefs; does not infer module routes."""
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit, urlunsplit, parse_qsl
from .config import is_within_admin_url, load_site_config
from .report_manager import save_report
from .seo_detector import detect, normalize

BLOCKED = re.compile(r'(^|[^a-z])(delete|remove|destroy|logout|save|update|insert|create|add|publish|unpublish|reset|clear|export|import|duplicate|clone|toggle|enable|disable|approve|reject)([^a-z]|$)', re.I)


def safe_url(base, href, admin_url=None):
    site = load_site_config()
    try:
        url = urljoin(base, href)
        parts = urlsplit(url)
    except (TypeError, ValueError):
        return None
    configured_admin_url = admin_url or site["admin_url"]
    if not is_within_admin_url(url, configured_admin_url):
        return None
    login_url = site["login_url"]
    if (
        BLOCKED.search(parts.path + '?' + parts.query)
        or (
            login_url
            and urlsplit(login_url).path.rstrip("/") == parts.path.rstrip("/")
        )
    ):
        return None
    for key, value in parse_qsl(parts.query):
        if key.lower() in {'action', 'act', 'do'} and value.lower() not in {'edit', 'view', 'list', 'index'}:
            return None
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ''))


def install_read_only_guard(context, blocked, admin_url=None):
    configured_admin_url = admin_url or load_site_config()["admin_url"]

    def guard(route):
        req = route.request
        is_admin_request = is_within_admin_url(
            req.url,
            configured_admin_url,
        )
        if req.method not in {'GET', 'HEAD', 'OPTIONS'} or (
            is_admin_request
            and not safe_url(req.url, req.url, configured_admin_url)
        ):
            blocked.append({'method': req.method, 'url': req.url})
            route.abort()
        else:
            route.continue_()
    context.route('**/*', guard)
    context.on('dialog', lambda dialog: dialog.dismiss())


def scan(page, folder, max_pages=1000, resume=False):
    import json
    from pathlib import Path

    path = Path(folder) / 'scan_report.json'
    site = load_site_config()
    if resume and path.exists():
        report = json.loads(path.read_text(encoding='utf-8'))
        if report.get('website') != site["website_url"]:
            raise RuntimeError(
                'Cannot resume: the saved report belongs to a different '
                'WEBSITE_URL. Start a new SCAN instead.'
            )
    else:
        if not safe_url(page.url, page.url, site["admin_url"]):
            raise RuntimeError(
                'SCAN must start from the configured website admin area.'
            )
        report = {'started_at': datetime.now(timezone.utc).isoformat(),
                  'website': site["website_url"], 'pages': [],
                  'pending': [{'url': page.url, 'module': 'Admin', 'record': 'Admin'}],
                  'excluded_links': [], 'blocked_requests': [], 'coverage': 'partial'}
    seen = {item['url'] for item in report['pages'] if item['status'] == 'scanned'}
    install_read_only_guard(
        page.context,
        report['blocked_requests'],
        load_site_config()["admin_url"],
    )
    count = 0
    while report['pending'] and count < max_pages:
        item = report['pending'][0]
        if item['url'] in seen:
            report['pending'].pop(0)
            continue
        target = safe_url(page.url, item['url'], site["admin_url"])
        if not target:
            report['excluded_links'].append({
                'source': page.url,
                'href': item['url'],
                'reason': 'Outside the configured website admin area.',
            })
            report['pending'].pop(0)
            save_report(folder, report)
            continue
        item['url'] = target
        try:
            for attempt in range(2):
                try:
                    response = page.goto(item['url'], wait_until='domcontentloaded', timeout=30000)
                    if response and response.status >= 400:
                        raise RuntimeError(f'HTTP {response.status}')
                    break
                except Exception:
                    if attempt:
                        raise
            login_url = load_site_config()["login_url"]
            if (
                (login_url and urlsplit(login_url).path.rstrip("/") == urlsplit(page.url).path.rstrip("/"))
                or page.locator('input[type=password]').count()
            ):
                report['stop_reason'] = 'Session expired. Login again before resuming.'
                break
            # Only activate explicit, non-submitting ARIA tabs with SEO text.
            tabs = page.get_by_role('tab')
            for i in range(tabs.count()):
                tab = tabs.nth(i)
                label = normalize(tab.inner_text())
                if ('seo' in label.split() or 'meta' in label.split()) and tab.is_visible():
                    tag = tab.evaluate('(e)=>({tag:e.tagName,type:e.type,href:e.getAttribute("href"),onclick:e.hasAttribute("onclick")})')
                    if not tag['onclick'] and ((tag['tag'] == 'BUTTON' and tag['type'] == 'button') or (tag['tag'] == 'A' and (tag['href'] or '').startswith('#'))):
                        tab.click(timeout=5000)
            module_name = normalize(item.get('module', ''))
            is_seo_page = any(
                term in module_name.split()
                for term in ('seo', 'page', 'trang', 'landing')
            )
            item['fields'] = detect(page, is_seopage=is_seo_page)
            item['status'] = 'scanned'
            item['title'] = page.title()
            links = page.locator('a[href]').evaluate_all('(els)=>els.map(e=>({href:e.getAttribute("href"),text:(e.innerText||e.getAttribute("title")||"").trim(),menu:!!e.closest("nav,aside,[role=navigation],.sidebar")}))')
            queued = {p['url'] for p in report['pending']} | seen
            for link in links:
                if not link['href'] or link['href'].startswith(('#', 'javascript:', 'mailto:')):
                    continue
                target = safe_url(
                    page.url,
                    link['href'],
                    load_site_config()["admin_url"],
                )
                if target and target not in queued:
                    report['pending'].append({'url': target, 'module': link['text'] if link['menu'] else item['module'], 'record': link['text'] or target})
                    queued.add(target)
                elif not target:
                    report['excluded_links'].append({'source': page.url, **link})
            seen.add(item['url'])
            logging.info('Scanned %s fields=%s', item['url'], [(f['key'], f['status']) for f in item['fields'] if f['key']])
        except Exception as error:
            item['status'] = 'error'
            item['error'] = str(error)
            logging.exception('Scan failed: %s', item['url'])
        report['pages'].append(dict(item))
        report['pending'].pop(0)
        count += 1
        save_report(folder, report)
    # Link crawling cannot prove coverage of JS-only menus or pagination.
    report['coverage'] = 'partial'
    report['limitations'] = ['Only discovered safe admin links are followed.', 'JavaScript-only menus, pagination, iframes and unrecognized SEO tabs need DOM review.', 'Blocked AJAX requests may prevent some data from loading.', 'No live-site selectors have been approved for UPDATE.']
    report['summary'] = {
        'modules': len({p['module'] for p in report['pages']}),
        'pages': len(report['pages']),
        'pages_with_seo': sum(any(f['status'] == 'identified' for f in p.get('fields', [])) for p in report['pages']),
        'identified_fields': sum(f['status'] == 'identified' for p in report['pages'] for f in p.get('fields', [])),
        'unrecognized_fields': sum(f['status'] != 'identified' for p in report['pages'] for f in p.get('fields', [])),
        'errors': sum(p['status'] == 'error' for p in report['pages']),
        'pending': len(report['pending'])}
    save_report(folder, report)
    return report
