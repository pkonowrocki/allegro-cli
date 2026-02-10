from __future__ import annotations

import sys

from allegro_cli.config import ensure_dirs, load_config, save_config
from allegro_cli.cookie_import import parse_cookie_table


def handle_login(args) -> int:
    ensure_dirs()
    print("Paste cookies from Chrome DevTools (Application > Cookies > allegro.pl).")
    print("You can paste the DevTools table OR a raw cookie header string.")
    print("Press Ctrl+Z then Enter (Windows) or Ctrl+D (Mac/Linux) when done:\n")

    try:
        text = sys.stdin.read()
    except KeyboardInterrupt:
        print("\nCancelled.")
        return 1

    text = text.strip()
    if not text:
        print("No input provided.", file=sys.stderr)
        return 1

    # Auto-detect format: if tabs or 2+ spaces → DevTools table, else raw string
    if "\t" in text or "  " in text:
        cookie_str = parse_cookie_table(text)
    else:
        # Raw cookie header string (e.g. "name1=val1; name2=val2")
        cookie_str = text

    if not cookie_str or "=" not in cookie_str:
        print("No cookies parsed. Check the format.", file=sys.stderr)
        return 1

    cookie_count = cookie_str.count("=")
    config = load_config()
    config.cookies = cookie_str
    save_config(config)

    print(f"\nSaved {cookie_count} cookies to config.")
    print("Try: allegro cart list")
    return 0
