# Orders Command Design

**Date:** 2026-07-14
**Scope:** v0.7.0 — `allegro orders` subcommand

## Overview

Add an `orders` top-level subcommand to allegro-cli with three subcommands: `list`, `reorder`, and `returns`. Uses the existing `edge.allegro.pl` httpx client (same cookie auth, same `_request()` pattern). No scraping required.

## Data Model

Two new dataclasses in `allegro_cli/api/models.py`:

```python
@dataclass
class OrderOffer:
    id: str
    title: str
    unitPrice: str        # e.g. "123.45 PLN"
    quantity: int
    imageUrl: str | None
    traits: list[str]     # ["CAN_BUY_AGAIN", ...]

@dataclass
class Order:
    id: str               # purchaseId — stable, human-visible
    seller: str           # seller.login
    sellerId: str         # seller.id — needed for reorder cart call
    offers: list[OrderOffer]
    status: str           # status.primary: SENT/DELIVERED/RETURNED/...
    totalCost: str        # e.g. "123.45 PLN"
    waybill: str | None   # delivery.waybillsData[0].waybillNumber if present
    orderDate: str        # first offer.orderDate
    canReorder: bool      # any offer has CAN_BUY_AGAIN trait
    returnStatus: str | None  # "RETURNED" / "RETURN_IN_PROGRESS" / None
```

`--compact` output per order: `id, seller, status, totalCost, canReorder, waybill, returnStatus`

## Client Method

Add to `AllegroClient` in `allegro_cli/api/client.py`:

```python
def get_orders(self, offset: int = 0, limit: int = 15) -> dict:
    resp = self._request(
        "GET", f"/myorders?offset={offset}&limit={limit}",
        accept="application/vnd.allegro.internal.v1+json",
    )
    return resp.json()
```

Returns raw dict. Mapping to `Order` dataclasses is done in the command handler (consistent with `get_cart` / `get_packages_list` pattern).

## Commands (`allegro_cli/commands/orders.py`)

### `handle_orders_list(args, client)`
- Calls `get_orders(offset=(args.page-1)*args.limit, limit=args.limit)`
- Maps `orderGroups` → `list[Order]` via `_parse_order()`
- Client-side filters: `--search` (title substring, case-insensitive), `--status` (exact match on `status.primary`)
- Output: json/compact/tsv/text — same pattern as `search.py`

### `handle_orders_reorder(args, client)`
- Fetches recent 50 orders, finds by `order.id == args.order_id`
- Filters offers to `CAN_BUY_AGAIN` trait
- Calls `change_cart_quantity(offer.id, delta=offer.quantity, seller_id=order.sellerId)` for each
- Errors: `OrderNotFoundException`, `CannotReorderException`
- Output: `{"reordered": N}` on success

### `handle_orders_returns(args, client)`
- Delegates to `handle_orders_list` with `args.status = "RETURNED"` pre-set
- Same output modes

## CLI Wiring (`allegro_cli/main.py`)

```
allegro orders list     [--limit N] [--page N] [--status STATUS] [--search TEXT]
allegro orders reorder  <order_id>
allegro orders returns  [--limit N] [--page N]
```

Shared flags inherited from parent parser: `--format`, `--compact`, `--verbose`.

## Error Handling

All errors via `output_error([make_error(...)])` to stderr as JSON:

| Code | Trigger |
|------|---------|
| `OrderNotFoundException` | order_id not in recent 50 orders |
| `CannotReorderException` | no `CAN_BUY_AGAIN` offers in order |
| `AuthenticationError` | propagated from `_request()` (401) |
| `RateLimitError` | propagated from `_request()` (403) |

## Tool Schema (`agent_specs/tools.json`)

Add three new tool definitions following existing schema pattern:
- `orders_list` — lists/filters orders
- `orders_reorder` — re-adds order items to cart
- `orders_returns` — lists orders with return status

## Testing

Add `tests/fixtures/get_myorders.json` with a representative response (2-3 order groups covering DELIVERED, SENT, RETURNED statuses, one with `CAN_BUY_AGAIN`). Add `tests/test_orders.py` using `MockAllegroClient`.

## Out of Scope

- Cursor/token-based pagination (offset works for now)
- Order detail endpoint (single order by ID)
- Creating returns/filing disputes
- API-side title search (client-side filter over 15-50 results is sufficient)
