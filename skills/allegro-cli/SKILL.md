---
name: allegro-cli
description: >-
  This skill should be used when the user asks to search Allegro.pl, find
  products or the cheapest offer, check product specifications, manage their
  Allegro shopping cart, track shipments, or anything related to the Allegro
  marketplace.
category: ecommerce
allowed-tools: [Bash]
---

# Allegro CLI Skill

This skill enables the agent to interact with the Allegro.pl marketplace using the `allegro` CLI. It is optimized for both human-readable output and LLM-friendly structured data.

## Trigger Conditions
Use this skill when the user:
- Wants to find a product on Allegro
- Asks for the cheapest/best offer for a specific item
- Wants to add/remove items from their Allegro shopping cart
- Needs to track a shipment from Allegro
- Wants to check product specifications (parameters) of an Allegro offer

## Installation & Setup
If the tool is not installed, install it via pip:
`pip install git+https://github.com/pkonowrocki/allegro-cli.git`

To register as a Claude Code skill (auto-discovered on next session):
`allegro skill`

**Authentication**:
The tool requires session cookies. If the agent detects authentication errors:
1. Instruct the user to run `allegro login`.
2. The user must paste their cookies from Chrome DevTools (Application > Cookies > allegro.pl).

## Workflows

### 1. Searching for Products
Always use `--format json --compact` to minimize token usage.

**Common filters**:
- **Condition**: `--condition new` or `--condition used`
- **Smart/Free delivery**: `--smart` or `--free-shipping` (same filter, aliases)
- **Speed**: `--delivery-time one_day`
- **Custom**: `--filter "key=value"` (e.g. `--filter "marka=Apple"`)
- **Sort**: `--sort p` (price asc), `--sort pd` (price desc)
- **Pagination**: `--page N` (default 1). Response includes `hasNextPage` and `nextPageUrl`.

**Compact search output**:
```json
{"offers": [{"id":"123","name":"Laptop","price":"1299.00","seller":"shop","url":"https://...","smart":true}], "page":1, "hasNextPage":true}
```
The `smart` field indicates Allegro Smart eligibility (free delivery with subscription).

**Example**: Find a new iPhone 15, cheapest first, with Allegro Smart:
`allegro search "iPhone 15" --condition new --smart --sort p --format json --compact`

### 2. Getting Offer Details
`allegro offer OFFER_ID --format json --compact`

Compact output includes: `id, name, price, seller, url, smart, parameters`.

### 3. Managing the Cart
- **List items**: `allegro cart list --format json --compact`
- **Add item**: `allegro cart add OFFER_ID SELLER_ID`
- **Remove item**: `allegro cart remove OFFER_ID SELLER_ID`

### 4. Tracking Packages
`allegro packages --format json --compact`

## Allegro Smart
Allegro Smart! is a subscription (59.90 PLN/yr) giving unlimited free delivery on eligible offers above 49.90 PLN. Use `--smart` or `--free-shipping` to filter search results. The `smart` field in compact output shows if an offer qualifies.

## Pitfalls
- **DataDome Block**: The CLI uses CloakBrowser (source-patched Chromium) to bypass bot protection. If it still fails, the user's cookies might be expired. Ask them to run `allegro login` again.
- **Empty Results**: Try loosening filters (e.g. remove `--smart` or `--delivery-time`).
- **Token Limits**: Always use `--format json --compact` for agent processing.

## Verification
- **Search**: Verify returned JSON contains offers with IDs, prices, and `smart` field.
- **Cart**: After adding an item, run `allegro cart list` to confirm.
- **Packages**: Verify the package list contains tracking numbers and statuses.
