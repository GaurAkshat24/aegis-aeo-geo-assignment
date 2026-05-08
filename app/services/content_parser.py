"""
content_parser.py
Fetches a URL and strips boilerplate HTML, returning cleaned text + raw HTML.
Handles JS-heavy pages gracefully by returning whatever html is available.
"""
from __future__ import annotations

import httpx
from bs4 import BeautifulSoup, NavigableString


_BOILERPLATE_TAGS = {"nav", "footer", "header", "aside", "script", "style", "noscript"}
_FETCH_TIMEOUT = 10.0


async def fetch_url(url: str) -> tuple[str, str]:
    """
    Fetch a URL and return (raw_html, error_detail).
    On success, error_detail is an empty string.
    On failure, raw_html is empty and error_detail describes the problem.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; AEGIS-AEO-Scanner/1.0; +https://aegis.ai)"
        )
    }
    try:
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=_FETCH_TIMEOUT
        ) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.text, ""
    except httpx.TimeoutException:
        return "", f"Connection timeout after {int(_FETCH_TIMEOUT)}s"
    except httpx.HTTPStatusError as exc:
        return "", f"HTTP {exc.response.status_code}: {exc.response.reason_phrase}"
    except httpx.RequestError as exc:
        return "", str(exc)


def html_to_text(html: str) -> str:
    """
    Parse HTML and return plain text with boilerplate removed.
    Preserves paragraph structure with double-newlines.
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(_BOILERPLATE_TAGS):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)


def strip_boilerplate(html: str) -> BeautifulSoup:
    """Return a BeautifulSoup tree with nav/footer/header/script removed."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(_BOILERPLATE_TAGS):
        tag.decompose()
    return soup


def extract_first_paragraph(html: str) -> str:
    """
    Extract the first non-empty paragraph.
    Falls back to the first text block if no <p> tags are found.
    """
    soup = strip_boilerplate(html)
    for p in soup.find_all("p"):
        text = p.get_text(strip=True)
        if len(text.split()) >= 3:
            return text

    # Plain text fallback — first non-empty block after splitting on blank lines
    text = soup.get_text(separator="\n", strip=True)
    for block in text.split("\n"):
        block = block.strip()
        if len(block.split()) >= 3:
            return block
    return text.strip()


def is_html(content: str) -> bool:
    """Heuristic — does the content look like HTML?"""
    return "<html" in content.lower() or "<p" in content.lower() or "<h" in content.lower()


def ensure_html(content: str) -> str:
    """
    If content is plain text, wrap it in minimal HTML so all parsers
    can work consistently.
    """
    if is_html(content):
        return content
    paragraphs = "\n".join(
        f"<p>{para.strip()}</p>"
        for para in content.split("\n\n")
        if para.strip()
    )
    return f"<html><body>{paragraphs}</body></html>"
