# allegro-cli

[![CI](https://github.com/pkonowrocki/allegro-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/pkonowrocki/allegro-cli/actions/workflows/ci.yml)

CLI for browsing [Allegro](https://allegro.pl) offers, managing your cart, and tracking packages. Designed to be both human-readable and LLM-agent friendly.

All output is available as aligned text tables, JSON, or TSV — pick what suits your workflow or pipe it into other tools.

## Install

```bash
pip install -e .
```

## Setup

Import cookies from your browser:

```bash
allegro login
```

Paste cookies from Chrome DevTools (Application > Cookies > allegro.pl). Both the DevTools table format and raw cookie header strings are accepted.

Alternatively, set cookies directly:

```bash
allegro config set --cookies 'cookie1=value1; cookie2=value2'
```

## Usage

### Search

```bash
allegro search "laptop"
allegro search "laptop" --category 491
allegro search "laptop" --category laptopy-491 --sort pd --price-min 2000 --price-max 5000
allegro search "laptop" --columns "id,name,sellingMode.price.amount,parameters"
```

| Flag | Description |
|------|-------------|
| `--category` | Category ID or slug (e.g. `491`, `laptopy-491`) |
| `--sort` | Sort order: `p` (price asc), `pd` (price desc), `m` (relevance), `n` (newest) |
| `--price-min` | Minimum price in PLN |
| `--price-max` | Maximum price in PLN |
| `--page` | Page number (default: 1) |
| `--columns` | Comma-separated columns to display |

### Offer details

```bash
allegro offer 12345678
allegro offer 12345678 --columns "name,sellingMode.price.amount,parameters"
```

Offer pages include a `parameters` field with product specifications (e.g. processor, RAM, screen size) extracted automatically from the listing.

### Cart

```bash
allegro cart list
allegro cart add OFFER_ID SELLER_ID --quantity 2
allegro cart remove OFFER_ID SELLER_ID
```

### Packages

```bash
allegro packages
```

### Configuration

```bash
allegro config show
allegro config set --output-format json
allegro config set --flaresolverr-url http://localhost:8191/v1
```

## Output formats

All commands support `--format text` (default), `--format json`, and `--format tsv`.

```bash
allegro search "laptop" --format json     # full JSON array
allegro search "laptop" --format tsv      # tab-separated, pipe-friendly
allegro search "laptop"                   # aligned text table (default)
allegro offer 12345678 --format json      # full offer with parameters
```

Use `--columns` to select specific fields (dot-notation supported):

```bash
allegro search "laptop" --columns "id,name,sellingMode.price.amount"
allegro offer 12345678 --columns "name,parameters"
```

Set a persistent default:

```bash
allegro config set --output-format json
```

## Anti-bot handling

Allegro uses anti-bot protection (DataDome). The CLI first tries a direct request with your cookies via `curl_cffi` (Chrome TLS fingerprint). If that gets a 403, it falls back to [FlareSolverr](https://github.com/FlareSolverr/FlareSolverr):

```bash
docker run -d --name flaresolverr -p 8191:8191 ghcr.io/flaresolverr/flaresolverr:latest
```

## Development

```bash
pip install -e ".[dev]"
pytest
```
