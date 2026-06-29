# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

allegro-cli — Python CLI for Allegro.pl marketplace: search, cart, package tracking. Designed for both human use and LLM agent consumption (token-efficient JSON output). Python 3.10+.

## Commands

```bash
pip install -e ".[dev]"    # install with dev deps
pytest                      # run all tests
pytest tests/test_cli.py    # run single test file
pytest -k "test_search"    # run tests matching name
python -m build             # build wheel
```

No linter or type checker is configured.

## Architecture

**Entry point**: `allegro_cli/main:cli` — argparse with subcommands (`search`, `offer`, `cart`, `packages`, `login`, `config`). Uses lazy imports inside `main()` for fast startup. Shared flags on a parent parser: `--format`, `--compact`, `--verbose`.

**Dual HTTP stack** (`allegro_cli/api/client.py`):
- `httpx.Client` for Edge API (`edge.allegro.pl`) — cart & packages (REST, cookie-auth)
- CloakBrowser (source-patched Chromium) for web scraping — defeats DataDome/Cloudflare via 58+ C++ fingerprint patches. Free tier by default, Pro via `cloakLicenseKey` config.

**Scraper** (`allegro_cli/scraper.py`): BeautifulSoup + lxml. Extracts offers from HTML. Also parses `<script id="__NEXT_DATA__">` JSON blocks. Handles Polish locale prices (e.g. "1 299,56 zł" → 1299.56).

**Commands** (`allegro_cli/commands/`): One module per subcommand. Each has handler functions called from main.

**Models & exceptions** (`allegro_cli/api/models.py`): Dataclasses for `Offer`, `Seller`, `Price`, etc. Exception hierarchy: `AllegroCliError` → `AuthenticationError`, `OfferNotFoundError`, `RateLimitError`, `ScraperError`, `CartError`. All exceptions carry `message`, `code`, `userMessage` for agent self-correction.

**Output** (`allegro_cli/output.py`): JSON (pretty or compact), rich tables (text), TSV (agent-friendly). Dot-path column access for nested fields (e.g. `sellingMode.price.amount`).

**Config** (`allegro_cli/config.py`): JSON at `~/.allegro-cli/config.json`, camelCase fields.

**Mock client** (`allegro_cli/api/mock_client.py`): Reads fixtures from `tests/fixtures/METHOD_PATH.json` for testing.

## Key Patterns

- `--compact` flag strips output to minimum fields for LLM token efficiency
- Cookie-based auth (users import browser cookies, no OAuth)
- CamelCase in JSON/API models, snake_case in Python code
- Python 3.10+ features used: `match` statements, `from __future__ import annotations`
- Cart item identification uses `item_id` (UUID), not `offer_id`
- Error output goes to stderr as JSON with structured codes
- Exit codes: 0 success, 1 general error, 2 auth error

## Conventions

- Conventional Commits + commitizen for versioning (auto-bump CI on merge to main)
- CI tests across Python 3.10–3.13
- `agent_specs/tools.json` defines LLM function-calling schemas mapping to CLI commands
