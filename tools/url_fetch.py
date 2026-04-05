#!/usr/bin/env python3
"""url_fetch — fetch and read the full content of a specific URL.

Input JSON: {"url": "<full URL to fetch>", "max_chars": <optional int, default 8000>}
Env: WORKSPACE — sandbox root (not used for fetching, but respected for context).

Fetches the URL, strips HTML tags to plain text, truncates to max_chars, prints to stdout.
"""
TOOL_DESC = 'fetch and read the full content of a specific URL.'
TOOL_MODE = 'observe'
TOOL_SCOPE = 'external'
TOOL_POST_OBSERVE = 'none'

import json, os, re, sys
import urllib.request
import urllib.error

MAX_RESULT_CHARS = 8000
DEFAULT_TIMEOUT = 15


def strip_html(html: str) -> str:
    """Strip HTML tags and decode common entities to plain text."""
    # Remove script and style blocks entirely
    html = re.sub(r'<(script|style)[^>]*>.*?</(script|style)>', '', html, flags=re.DOTALL | re.IGNORECASE)
    # Remove all remaining tags
    text = re.sub(r'<[^>]+>', ' ', html)
    # Decode common HTML entities
    entities = {
        '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"',
        '&#39;': "'", '&nbsp;': ' ', '&mdash;': '—', '&ndash;': '–',
        '&lsquo;': '\u2018', '&rsquo;': '\u2019', '&ldquo;': '\u201c', '&rdquo;': '\u201d',
    }
    for entity, char in entities.items():
        text = text.replace(entity, char)
    # Decode numeric entities
    text = re.sub(r'&#(\d+);', lambda m: chr(int(m.group(1))), text)
    text = re.sub(r'&#x([0-9a-fA-F]+);', lambda m: chr(int(m.group(1), 16)), text)
    # Collapse whitespace
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def fetch_url(url: str, max_chars: int, timeout: int = DEFAULT_TIMEOUT) -> str:
    """Fetch URL and return plain text content, truncated to max_chars."""
    # Basic URL validation
    if not url.startswith(('http://', 'https://')):
        return f"Error: URL must start with http:// or https:// — got: {url[:100]}"

    headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; url_fetch/1.0)',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.7',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            # Read up to 2MB raw (enough to extract text)
            raw = resp.read(2 * 1024 * 1024)
            content_type = resp.headers.get('Content-Type', '')

            # Detect encoding
            encoding = 'utf-8'
            ct_match = re.search(r'charset=([\w-]+)', content_type, re.IGNORECASE)
            if ct_match:
                encoding = ct_match.group(1)

            try:
                text = raw.decode(encoding, errors='replace')
            except (LookupError, UnicodeDecodeError):
                text = raw.decode('utf-8', errors='replace')

            # Strip HTML if it looks like HTML
            if '<html' in text[:2000].lower() or '<!doctype' in text[:200].lower() or '<body' in text[:2000].lower():
                text = strip_html(text)
            else:
                # Plain text or JSON — just clean whitespace
                text = re.sub(r'[ \t]+', ' ', text)
                text = re.sub(r'\n{4,}', '\n\n\n', text).strip()

            final_url = resp.url if hasattr(resp, 'url') else url

    except urllib.error.HTTPError as e:
        return f"Error: HTTP {e.code} {e.reason} — {url}"
    except urllib.error.URLError as e:
        return f"Error: URL fetch failed — {e.reason}"
    except TimeoutError:
        return f"Error: request timed out after {timeout}s — {url}"
    except Exception as e:
        return f"Error: {type(e).__name__}: {e}"

    # Truncate
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n... [truncated at {max_chars} chars]"

    return f"URL: {final_url}\n\n{text}"


def main():
    params = json.load(sys.stdin)
    url = params.get('url', '').strip()
    max_chars = params.get('max_chars', MAX_RESULT_CHARS)

    if not url:
        print('Error: missing \'url\' parameter', file=sys.stderr)
        sys.exit(1)

    if not isinstance(max_chars, int) or max_chars <= 0:
        max_chars = MAX_RESULT_CHARS
    max_chars = min(max_chars, 32000)  # hard cap

    result = fetch_url(url, max_chars)
    print(result)


if __name__ == '__main__':
    main()
