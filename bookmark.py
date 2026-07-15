import hashlib
import html
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from IPython.display import HTML


# 缓存统一保存在 bookmark.py 所在目录
CACHE_DIR = Path(__file__).resolve().parent / ".bookmark-cache"
CACHE_DIR.mkdir(exist_ok=True)


def _cache_path(url):
    """根据网址生成唯一的缓存文件名。"""
    key = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return CACHE_DIR / f"{key}.json"


def _read_cache(url):
    """读取已有缓存。"""
    path = _cache_path(url)

    if not path.exists():
        return None

    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError):
        return None


def _write_cache(url, data):
    """将网页信息写入缓存。"""
    path = _cache_path(url)

    try:
        with path.open("w", encoding="utf-8") as file:
            json.dump(
                data,
                file,
                ensure_ascii=False,
                indent=2
            )
    except OSError:
        pass


def _meta_property(soup, property_name):
    """读取 property="..." 类型的 meta 标签。"""
    tag = soup.find(
        "meta",
        attrs={"property": property_name}
    )

    if tag:
        return tag.get("content", "").strip()

    return ""


def _meta_name(soup, name):
    """读取 name="..." 类型的 meta 标签。"""
    tag = soup.find(
        "meta",
        attrs={"name": name}
    )

    if tag:
        return tag.get("content", "").strip()

    return ""


def _first_nonempty(*values):
    """返回第一个非空值。"""
    for value in values:
        if value:
            return str(value).strip()

    return ""


def _format_date(date_string):
    """尽量把发布日期统一为 YYYY-MM-DD。"""
    if not date_string:
        return ""

    clean = date_string.strip()

    try:
        parsed = datetime.fromisoformat(
            clean.replace("Z", "+00:00")
        )
        return parsed.strftime("%Y-%m-%d")
    except ValueError:
        return clean


def _find_favicon(soup, url):
    """查找网页 favicon。"""
    icon_tag = soup.find(
        "link",
        rel=lambda value: (
            value
            and "icon" in (
                " ".join(value)
                if isinstance(value, list)
                else value
            ).lower()
        )
    )

    if icon_tag:
        favicon = icon_tag.get("href", "").strip()

        if favicon:
            return urljoin(url, favicon)

    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}/favicon.ico"


def _fetch_metadata(url):
    """联网读取网页的标题、简介、作者、日期和图片。"""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/120 Safari/537.36"
        )
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=15
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    title = _first_nonempty(
        _meta_property(soup, "og:title"),
        _meta_name(soup, "twitter:title"),
        soup.title.get_text(strip=True)
        if soup.title else ""
    )

    description = _first_nonempty(
        _meta_property(soup, "og:description"),
        _meta_name(soup, "twitter:description"),
        _meta_name(soup, "description")
    )

    site_name = _first_nonempty(
        _meta_property(soup, "og:site_name"),
        urlparse(url).netloc
    )

    author = _first_nonempty(
        _meta_name(soup, "author"),
        _meta_property(soup, "article:author"),
        _meta_name(soup, "byl")
    )

    published = _first_nonempty(
        _meta_property(soup, "article:published_time"),
        _meta_name(soup, "date"),
        _meta_name(soup, "publication_date"),
        _meta_name(soup, "pubdate"),
        _meta_name(soup, "DC.date")
    )

    image = _first_nonempty(
        _meta_property(soup, "og:image"),
        _meta_name(soup, "twitter:image")
    )

    if image:
        image = urljoin(url, image)

    favicon = _find_favicon(soup, url)

    return {
        "url": url,
        "title": title,
        "description": description,
        "site_name": site_name,
        "author": author,
        "published": _format_date(published),
        "image": image,
        "favicon": favicon,
        "cached_at": datetime.now(
            timezone.utc
        ).isoformat()
    }


def bookmark(url, refresh=False):
    """
    生成网页书签卡片。

    Parameters
    ----------
    url : str
        网页链接。

    refresh : bool
        False：优先读取缓存。
        True：忽略旧缓存，重新联网抓取。
    """

    data = None

    if not refresh:
        data = _read_cache(url)

    if data is None:
        try:
            data = _fetch_metadata(url)
            _write_cache(url, data)

        except requests.RequestException:
            data = {
                "url": url,
                "title": url,
                "description": "Could not retrieve webpage metadata.",
                "site_name": urlparse(url).netloc,
                "author": "",
                "published": "",
                "image": "",
                "favicon": ""
            }

    safe_url = html.escape(
        data.get("url", ""),
        quote=True
    )

    safe_title = html.escape(
        data.get("title", "") or safe_url
    )

    safe_description = html.escape(
        data.get("description", "")
    )

    safe_site = html.escape(
        data.get("site_name", "")
    )

    safe_author = html.escape(
        data.get("author", "")
    )

    safe_date = html.escape(
        data.get("published", "")
    )

    safe_image = html.escape(
        data.get("image", ""),
        quote=True
    )

    safe_favicon = html.escape(
        data.get("favicon", ""),
        quote=True
    )

    favicon_html = ""

    if safe_favicon:
        favicon_html = f"""
<img
  class="bookmark-favicon"
  src="{safe_favicon}"
  alt=""
>
"""

    metadata_parts = []

    if safe_author:
        metadata_parts.append(
            f'<span class="bookmark-author">{safe_author}</span>'
        )

    if safe_date:
        metadata_parts.append(
            f'<span class="bookmark-date">{safe_date}</span>'
        )

    metadata_html = ""

    if metadata_parts:
        separator = (
            '<span class="bookmark-separator">·</span>'
        )

        metadata_html = f"""
<div class="bookmark-meta">
  {separator.join(metadata_parts)}
</div>
"""

    description_html = ""

    if safe_description:
        description_html = f"""
<div class="bookmark-description">
  {safe_description}
</div>
"""

    image_html = ""

    if safe_image:
        image_html = f"""
<div class="bookmark-right">
  <img
    class="bookmark-image"
    src="{safe_image}"
    alt=""
  >
</div>
"""

    card_html = f"""
<div class="bookmark-card">

  <div class="bookmark-left">

    <div class="bookmark-site-row">
      {favicon_html}
      <span class="bookmark-site">{safe_site}</span>
    </div>

    <div class="bookmark-title">
      <a
        href="{safe_url}"
        target="_blank"
        rel="noopener noreferrer"
      >
        {safe_title}
      </a>
    </div>

    {description_html}

    {metadata_html}

  </div>

  {image_html}

</div>
"""

    return HTML(card_html)