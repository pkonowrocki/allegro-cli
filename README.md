# 🛒 allegro-cli

[![CI](https://github.com/pkonowrocki/allegro-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/pkonowrocki/allegro-cli/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://spdx.org/licenses/mit.html)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

**The power-user's gateway to Allegro.**

`allegro-cli` is a high-performance command-line interface for browsing offers, managing carts, and tracking packages on Allegro.pl. It is designed for two types of users: **power-users** who want to automate their shopping and **AI Agents** who need structured, token-efficient access to marketplace data.

---

## ✨ Key Features

- **🚀 Agent-First Design**: Optimized JSON outputs (`--compact`) to minimize LLM token usage while maximizing data density.
- **🎨 Rich UX**: Beautifully formatted, color-coded tables for humans.
- **🔍 Advanced Filtering**: Precision search with filters for condition, free shipping, Allegro Smart, and delivery speed.
- **📦 Full Tracking**: Detailed package tracking beyond simple summaries.
- **🛡️ Bot Bypass**: Integrated TLS fingerprinting via `curl_cffi` to transparently handle anti-bot protections (DataDome) without external dependencies.
- **🛠️ Extensible**: Pure Python implementation, easy to integrate into larger automation pipelines.

---

## 🚀 Quick Start

### Installation

**From GitHub Releases** (recommended):
```bash
pip install https://github.com/pkonowrocki/allegro-cli/releases/latest/download/allegro_cli-0.6.0-py3-none-any.whl
```

**From source (latest)**:
```bash
pip install git+https://github.com/pkonowrocki/allegro-cli.git
```

### Setup

To access personalized data (cart, packages), you need to provide your session cookies:

```bash
allegro login
```
*Follow the prompt to paste your cookies from Chrome DevTools (Application $\rightarrow$ Cookies $\rightarrow$ allegro.pl).*

---

## 📖 Usage

### 🔍 Search for Products
Find exactly what you need with advanced filters:

```bash
# Basic search
allegro search "kawa ziarnista"

# Power-user search: New, with Allegro Smart, delivered in 1 day, sorted by price ascending
allegro search "kawa ziarnista" --condition new --smart --delivery-time one_day --sort p

# Filter by custom criteria (e.g., specific brand or parameter)
allegro search "laptop" --filter "marka=Apple"

# Search on a specific seller's page
allegro search "kawa" --seller Muvepl

# Price range
allegro search "laptop" --price-min 1000 --price-max 3000

# Allegro Pay offers only
allegro search "iphone" --pay
```

**Search Flags:**
| Flag | Description | Examples |
|------|-------------|----------|
| `--category` | Category ID or slug | `491`, `laptopy-491` |
| `--sort` | `p` (price ↑), `pd` (price ↓), `m` (relevance), `n` (newest) | `--sort pd` |
| `--condition` | Product condition (can specify multiple) | `--condition new`, `--condition new used` |
| `--smart` | Filter for Allegro Smart | `--smart` |
| `--free-shipping`| Only free delivery | `--free-shipping` |
| `--delivery-time`| Delivery speed | `one_day`, `two_day`, `three_day` |
| `--price-min` | Minimum price in PLN | `--price-min 100` |
| `--price-max` | Maximum price in PLN | `--price-max 500` |
| `--seller` | Search on seller's page | `--seller Muvepl` |
| `--pay` | Filter for Allegro Pay | `--pay` |
| `--location` | Shipping location | `--location polska` |
| `--filter` | Key=Value custom filter (repeatable) | `--filter "color=black"` |
| `--columns` | Custom output columns | `--columns id,name,seller.name` |

### 📦 Manage Your Shopping

**Offers:**
```bash
# Get full details and extracted product specifications
allegro offer 12345678
```

**Cart:**
```bash
allegro cart list                      # View current items
allegro cart add OFFER_ID              # Add item to cart (seller auto-detected)
allegro cart add OFFER_ID SELLER_ID    # Add item with explicit seller
allegro cart add OFFER_ID --quantity 3 # Add multiple units
allegro cart remove OFFER_ID           # Remove item from cart
```

**Tracking:**
```bash
allegro packages            # List all active shipments with detailed status
```

---

## 🤖 For AI Agents (LLM Optimization)

If you are building an AI agent, use the `--format json` and `--compact` flags. The compact mode strips unnecessary metadata to save tokens while keeping all critical data points.

```bash
allegro search "mechanical keyboard" --format json --compact
```

---

## 🛠️ Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run the test suite (including Mock Client tests)
pytest
```

## 📜 License

Distributed under the MIT License. See `LICENSE` for more information.
