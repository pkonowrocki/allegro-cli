---
name: allegro-cli
description: High-performance CLI for browsing Allegro.pl, managing carts, and tracking packages.
category: ecommerce
---

# Allegro CLI Skill

This skill enables the agent to interact with the Allegro.pl marketplace using the `allegro-cli` tool. It is optimized for both human-readable output and LLM-friendly structured data.

## 🎯 Trigger Conditions
Use this skill when the user:
- Wants to find a product on Allegro.
- Asks for the cheapest/best offer for a specific item on Allegro.
- Wants to add/remove items from their Allegro shopping cart.
- Needs to track a shipment from Allegro.
- Wants to check product specifications (parameters) of an Allegro offer.

## 🛠 Installation & Setup
If the tool is not installed, install it via pip:
`pip install git+https://github.com/pkonowrocki/allegro-cli.git`

**Authentication**:
The tool requires session cookies. If the agent detects authentication errors:
1. Instruct the user to run `allegro login`.
2. The user must paste their cookies from Chrome DevTools ($\rightarrow$ Application $\rightarrow$ Cookies $\rightarrow$ allegro.pl).

## 🚀 Workflows

### 1. Searching for Products
To find products, use `allegro search`. 
**Crucial for Agents**: Always use `--format json --compact` to minimize token usage and get structured data.

**Common filters**:
- **Condition**: `--condition new` or `--condition used`
- **Smart**: `--smart` (Allegro Smart delivery)
- **Shipping**: `--free-shipping`
- **Speed**: `--delivery-time one_day`
- **Custom**: `--filter "key=value"` (e.g., `--filter "marka=Apple"`)
- **Sort**: `--sort p` (price asc), `--sort pd` (price desc)

**Example**: Find a new iPhone 15, cheapest first, with Allegro Smart:
`allegro search "iPhone 15" --condition new --smart --sort p --format json --compact`

### 2. Getting Offer Details
To get detailed specifications of a product:
`allegro offer OFFER_ID --format json --compact`

### 3. Managing the Cart
- **List items**: `allegro cart list --format json --compact`
- **Add item**: `allegro cart add OFFER_ID SELLER_ID`
- **Remove item**: `allegro cart remove OFFER_ID SELLER_ID`

### 4. Tracking Packages
To get the status of all active shipments:
`allegro packages --format json --compact`

## ⚠️ Pitfalls & Troubleshooting
- **DataDome Block**: The CLI uses `curl_cffi` to bypass bot protection. If it still fails, the user's cookies might be expired. Ask them to run `allegro login` again.
- **Empty Results**: If a search returns no results, try loosening the filters (e.g., remove `--smart` or `--delivery-time`).
- **Token Limits**: Never use the default `text` format for large search results when processing data for the user; always use `--format json --compact`.

## ✅ Verification
- **Search**: Verify that the returned JSON contains a list of offers with IDs and prices.
- **Cart**: After adding an item, run `allegro cart list` to confirm it appears.
- **Packages**: Verify that the package list contains tracking numbers and current statuses.
