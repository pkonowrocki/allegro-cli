"""Parse cookies from Chrome DevTools table format into Cookie header string."""
from __future__ import annotations

import re


def parse_cookie_table(text: str) -> str:
    """Parse Chrome DevTools cookie table (tab/space separated) into Cookie header string.

    Each line: Name  Value  Domain  Path  Expires  Size  [HttpOnly]  [Secure]  [SameSite]  ...
    """
    cookies = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        # Split on tabs or multiple spaces
        parts = re.split(r"\t+|\s{2,}", line)
        if len(parts) >= 2:
            name = parts[0].strip()
            value = parts[1].strip()
            if name and not name.startswith("#"):
                cookies.append(f"{name}={value}")
    return "; ".join(cookies)
