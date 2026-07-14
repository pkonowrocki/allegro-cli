# Orders Command Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `allegro orders list|reorder|returns` subcommand using the existing edge.allegro.pl httpx client.

**Architecture:** New `commands/orders.py` handler mirrors the `packages.py` pattern — raw dict from `client.get_orders()` mapped to `Order` dataclasses in the handler. Two new exception subclasses. CLI wired into `main.py` with nested subparsers matching the `cart` pattern.

**Tech Stack:** Python 3.10+, httpx (already in project), argparse, dataclasses, pytest

## Global Constraints

- Python 3.10+ (`from __future__ import annotations`, `match` statements)
- CamelCase in JSON/dataclass fields, snake_case in Python args
- All errors → `output_error([make_error(...)])` to stderr as JSON; never `print("Error: ...")`
- Exit codes: 0 success, 1 general error, 2 auth error
- `--compact` must strip to minimal fields for LLM token efficiency
- Run `pytest` after every task to confirm no regressions

---

### Task 1: Models — OrderOffer, Order, new exceptions

**Files:**
- Modify: `allegro_cli/api/models.py`

**Interfaces:**
- Produces: `OrderOffer(id, title, unitPrice, quantity, imageUrl, traits)`, `Order(id, seller, sellerId, offers, status, totalCost, waybill, orderDate, canReorder, returnStatus)`, `OrderNotFoundException(order_id)`, `CannotReorderException(order_id)`

- [ ] **Step 1: Write the failing import test**

Add to `tests/test_orders.py` (create the file):

```python
from allegro_cli.api.models import Order, OrderOffer, OrderNotFoundException, CannotReorderException


def test_order_models_importable():
    offer = OrderOffer(
        id="offer-1",
        title="Test Product",
        unitPrice="99.99 PLN",
        quantity=2,
        imageUrl=None,
        traits=["CAN_BUY_AGAIN"],
    )
    order = Order(
        id="order-abc",
        seller="testshop",
        sellerId="seller-1",
        offers=[offer],
        status="DELIVERED",
        totalCost="199.98 PLN",
        waybill="PL123456789",
        orderDate="2026-01-15T10:00:00Z",
        canReorder=True,
        returnStatus=None,
    )
    assert order.canReorder is True
    assert order.offers[0].traits == ["CAN_BUY_AGAIN"]


def test_order_not_found_exception():
    exc = OrderNotFoundException("order-xyz")
    assert exc.code == "OrderNotFoundException"
    assert "order-xyz" in exc.message


def test_cannot_reorder_exception():
    exc = CannotReorderException("order-xyz")
    assert exc.code == "CannotReorderException"
    assert "order-xyz" in exc.message
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_orders.py -v
```
Expected: `ImportError: cannot import name 'Order'`

- [ ] **Step 3: Add models to `allegro_cli/api/models.py`**

Append after the `SearchResult` dataclass (before `# --- Exceptions ---`):

```python
@dataclass
class OrderOffer:
    id: str
    title: str
    unitPrice: str        # e.g. "99.99 PLN"
    quantity: int
    imageUrl: str | None
    traits: list[str]     # e.g. ["CAN_BUY_AGAIN"]


@dataclass
class Order:
    id: str               # purchaseId — stable, human-visible
    seller: str           # seller.login
    sellerId: str         # seller.id — required for reorder cart call
    offers: list[OrderOffer]
    status: str           # status.primary: SENT/DELIVERED/RETURNED/...
    totalCost: str        # e.g. "199.98 PLN"
    waybill: str | None   # waybillsData[0].waybillNumber or None
    orderDate: str        # first offer.orderDate
    canReorder: bool      # any offer has "CAN_BUY_AGAIN" in traits
    returnStatus: str | None  # "RETURNED" / "RETURN_IN_PROGRESS" / None
```

Add after `CartError` in the exceptions block:

```python
class OrderNotFoundException(AllegroCliError):
    def __init__(self, order_id: str):
        super().__init__(
            message=f"Order {order_id} not found",
            code="OrderNotFoundException",
            userMessage=f"Order {order_id} was not found in recent orders.",
        )


class CannotReorderException(AllegroCliError):
    def __init__(self, order_id: str):
        super().__init__(
            message=f"No reorderable items in order {order_id}",
            code="CannotReorderException",
            userMessage=f"None of the items in order {order_id} can be reordered (CAN_BUY_AGAIN trait missing).",
        )
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_orders.py -v
```
Expected: all 3 tests PASS

- [ ] **Step 5: Run full suite to confirm no regressions**

```bash
pytest
```
Expected: all existing tests PASS

- [ ] **Step 6: Commit**

```bash
git add allegro_cli/api/models.py tests/test_orders.py
git commit -m "feat: add Order/OrderOffer models and order exception types"
```

---

### Task 2: Client method + test fixture

**Files:**
- Modify: `allegro_cli/api/client.py`
- Create: `tests/fixtures/get_myorders.json`

**Interfaces:**
- Consumes: `AllegroClient._request()` (existing), `AllegroClient._require_edge()` (existing)
- Produces: `AllegroClient.get_orders(offset: int = 0, limit: int = 15) -> dict`

- [ ] **Step 1: Create the test fixture**

Create `tests/fixtures/get_myorders.json`:

```json
{
  "status_code": 200,
  "body": {
    "orderGroups": [
      {
        "groupId": "group-1",
        "myorders": [
          {
            "id": "order-delivered-1",
            "seller": {"id": "seller-100", "login": "bestshop"},
            "offers": [
              {
                "id": "offer-aaa",
                "title": "Laptop Dell XPS 15",
                "unitPrice": "4999.00 PLN",
                "quantity": 1,
                "imageUrl": "https://img.allegrostatic.pl/foo.jpg",
                "orderDate": "2026-06-01T12:00:00Z",
                "traits": ["CAN_BUY_AGAIN"]
              }
            ],
            "delivery": {
              "status": "DELIVERED",
              "waybillsData": [{"waybillNumber": "PL123456789"}]
            },
            "totalCost": {"amount": "4999.00", "currency": "PLN"},
            "status": {"primary": "DELIVERED", "actions": []}
          }
        ]
      },
      {
        "groupId": "group-2",
        "myorders": [
          {
            "id": "order-sent-2",
            "seller": {"id": "seller-200", "login": "techstore"},
            "offers": [
              {
                "id": "offer-bbb",
                "title": "Mechanical Keyboard",
                "unitPrice": "299.00 PLN",
                "quantity": 1,
                "imageUrl": null,
                "orderDate": "2026-06-10T09:00:00Z",
                "traits": []
              }
            ],
            "delivery": {
              "status": "SENT",
              "waybillsData": [{"waybillNumber": "PL987654321"}]
            },
            "totalCost": {"amount": "299.00", "currency": "PLN"},
            "status": {"primary": "SENT", "actions": []}
          }
        ]
      },
      {
        "groupId": "group-3",
        "myorders": [
          {
            "id": "order-returned-3",
            "seller": {"id": "seller-300", "login": "gadgetworld"},
            "offers": [
              {
                "id": "offer-ccc",
                "title": "Wireless Mouse",
                "unitPrice": "89.00 PLN",
                "quantity": 2,
                "imageUrl": null,
                "orderDate": "2026-05-20T15:00:00Z",
                "traits": []
              }
            ],
            "delivery": {
              "status": "RETURNED",
              "waybillsData": []
            },
            "totalCost": {"amount": "178.00", "currency": "PLN"},
            "status": {"primary": "RETURNED", "actions": []}
          }
        ]
      }
    ],
    "total": 3,
    "offset": 0
  }
}
```

- [ ] **Step 2: Write the failing test**

Add to `tests/test_orders.py`:

```python
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from allegro_cli.api.mock_client import MockAllegroClient
from allegro_cli.config import Config


def _make_mock_client():
    config = Config(cookies="session=x", edgeBaseUrl="https://edge.allegro.pl")
    return MockAllegroClient(config, fixtures_path="tests/fixtures")


def test_get_orders_returns_dict():
    client = _make_mock_client()
    result = client.get_orders()
    assert isinstance(result, dict)
    assert "orderGroups" in result
    assert result["total"] == 3
    assert len(result["orderGroups"]) == 3
```

- [ ] **Step 3: Run test to verify it fails**

```bash
pytest tests/test_orders.py::test_get_orders_returns_dict -v
```
Expected: FAIL — `AllegroClient has no attribute 'get_orders'`

- [ ] **Step 4: Add `get_orders()` to `AllegroClient`**

In `allegro_cli/api/client.py`, add after `get_packages_list()`:

```python
def get_orders(self, offset: int = 0, limit: int = 15) -> dict:
    """Fetch paginated order history from edge.allegro.pl/myorders."""
    resp = self._request(
        "GET", f"/myorders?offset={offset}&limit={limit}",
        accept="application/vnd.allegro.internal.v1+json",
    )
    return resp.json()
```

- [ ] **Step 5: Run test**

```bash
pytest tests/test_orders.py::test_get_orders_returns_dict -v
```
Expected: PASS

- [ ] **Step 6: Run full suite**

```bash
pytest
```
Expected: all tests PASS

- [ ] **Step 7: Commit**

```bash
git add allegro_cli/api/client.py tests/fixtures/get_myorders.json tests/test_orders.py
git commit -m "feat: add get_orders() client method and myorders fixture"
```

---

### Task 3: Command handler (`commands/orders.py`)

**Files:**
- Create: `allegro_cli/commands/orders.py`

**Interfaces:**
- Consumes: `AllegroClient.get_orders(offset, limit) -> dict`, `AllegroClient.change_cart_quantity(item_id, delta, seller_id)`, `Order`, `OrderOffer`, `OrderNotFoundException`, `CannotReorderException`, `output_json`, `output_tsv`, `output_text`, `output_error`, `make_error`
- Produces: `handle_orders_list(args, client) -> int`, `handle_orders_reorder(args, client) -> int`, `handle_orders_returns(args, client) -> int`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_orders.py`:

```python
import sys
from io import StringIO

from allegro_cli.commands.orders import handle_orders_list, handle_orders_reorder, handle_orders_returns


def _make_args(**kwargs):
    args = MagicMock()
    args.format = "json"
    args.compact = False
    args.page = 1
    args.limit = 15
    args.search = None
    args.status = None
    for k, v in kwargs.items():
        setattr(args, k, v)
    return args


def test_handle_orders_list_json(capsys):
    client = _make_mock_client()
    args = _make_args()
    result = handle_orders_list(args, client)
    assert result == 0
    data = json.loads(capsys.readouterr().out)
    assert "orders" in data
    assert len(data["orders"]) == 3


def test_handle_orders_list_filter_by_status(capsys):
    client = _make_mock_client()
    args = _make_args(status="DELIVERED")
    result = handle_orders_list(args, client)
    assert result == 0
    data = json.loads(capsys.readouterr().out)
    assert all(o["status"] == "DELIVERED" for o in data["orders"])


def test_handle_orders_list_filter_by_search(capsys):
    client = _make_mock_client()
    args = _make_args(search="laptop")
    result = handle_orders_list(args, client)
    assert result == 0
    data = json.loads(capsys.readouterr().out)
    assert len(data["orders"]) == 1
    assert data["orders"][0]["id"] == "order-delivered-1"


def test_handle_orders_list_compact(capsys):
    client = _make_mock_client()
    args = _make_args(compact=True)
    result = handle_orders_list(args, client)
    assert result == 0
    data = json.loads(capsys.readouterr().out)
    order = data["orders"][0]
    assert set(order.keys()) == {"id", "seller", "status", "totalCost", "canReorder", "waybill", "returnStatus"}


def test_handle_orders_returns_filters_to_returned(capsys):
    client = _make_mock_client()
    args = _make_args()
    result = handle_orders_returns(args, client)
    assert result == 0
    data = json.loads(capsys.readouterr().out)
    assert all(o["status"] in ("RETURNED", "RETURN_IN_PROGRESS") for o in data["orders"])


def test_handle_orders_reorder_success(capsys):
    client = _make_mock_client()
    client.change_cart_quantity = MagicMock(return_value=None)
    args = _make_args(order_id="order-delivered-1")
    result = handle_orders_reorder(args, client)
    assert result == 0
    data = json.loads(capsys.readouterr().out)
    assert data["reordered"] == 1
    client.change_cart_quantity.assert_called_once_with("offer-aaa", delta=1, seller_id="seller-100")


def test_handle_orders_reorder_not_found(capsys):
    client = _make_mock_client()
    args = _make_args(order_id="nonexistent-order")
    result = handle_orders_reorder(args, client)
    assert result == 1
    err = json.loads(capsys.readouterr().err)
    assert err["errors"][0]["code"] == "OrderNotFoundException"


def test_handle_orders_reorder_cannot_reorder(capsys):
    client = _make_mock_client()
    # order-sent-2 has no CAN_BUY_AGAIN trait
    args = _make_args(order_id="order-sent-2")
    result = handle_orders_reorder(args, client)
    assert result == 1
    err = json.loads(capsys.readouterr().err)
    assert err["errors"][0]["code"] == "CannotReorderException"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_orders.py -k "handle_orders" -v
```
Expected: `ImportError: cannot import name 'handle_orders_list'`

- [ ] **Step 3: Create `allegro_cli/commands/orders.py`**

```python
from __future__ import annotations

import dataclasses

from allegro_cli.api.client import AllegroClient
from allegro_cli.api.models import (
    CannotReorderException,
    Order,
    OrderNotFoundException,
    OrderOffer,
)
from allegro_cli.output import make_error, output_error, output_json, output_text, output_tsv


def _parse_order(myorder: dict) -> Order:
    offers = [
        OrderOffer(
            id=o["id"],
            title=o.get("title", ""),
            unitPrice=o.get("unitPrice", ""),
            quantity=o.get("quantity", 1),
            imageUrl=o.get("imageUrl"),
            traits=o.get("traits", []),
        )
        for o in myorder.get("offers", [])
    ]
    waybills = myorder.get("delivery", {}).get("waybillsData", [])
    waybill = waybills[0]["waybillNumber"] if waybills else None
    status_primary = myorder.get("status", {}).get("primary", "UNKNOWN")
    total = myorder.get("totalCost", {})
    total_str = f"{total.get('amount', '0')} {total.get('currency', 'PLN')}"
    order_date = offers[0].orderDate if offers else ""
    can_reorder = any("CAN_BUY_AGAIN" in o.traits for o in offers)
    return_status = status_primary if status_primary in ("RETURNED", "RETURN_IN_PROGRESS") else None
    return Order(
        id=myorder["id"],
        seller=myorder.get("seller", {}).get("login", ""),
        sellerId=myorder.get("seller", {}).get("id", ""),
        offers=offers,
        status=status_primary,
        totalCost=total_str,
        waybill=waybill,
        orderDate=order_date,
        canReorder=can_reorder,
        returnStatus=return_status,
    )


def _compact_order(order: Order) -> dict:
    return {
        "id": order.id,
        "seller": order.seller,
        "status": order.status,
        "totalCost": order.totalCost,
        "canReorder": order.canReorder,
        "waybill": order.waybill,
        "returnStatus": order.returnStatus,
    }


def handle_orders_list(args, client: AllegroClient) -> int:
    offset = (args.page - 1) * args.limit
    raw = client.get_orders(offset=offset, limit=args.limit)
    orders = [
        _parse_order(myorder)
        for group in raw.get("orderGroups", [])
        for myorder in group.get("myorders", [])
    ]

    if args.search:
        term = args.search.lower()
        orders = [o for o in orders if any(term in of.title.lower() for of in o.offers)]
    if args.status:
        orders = [o for o in orders if o.status == args.status.upper()]

    if args.format == "json":
        if args.compact:
            output_json({"orders": [_compact_order(o) for o in orders]})
        else:
            output_json({
                "orders": [dataclasses.asdict(o) for o in orders],
                "total": raw.get("total", len(orders)),
            })
    elif args.format == "tsv":
        output_tsv(
            [dataclasses.asdict(o) for o in orders],
            columns=["id", "seller", "status", "totalCost", "waybill"],
        )
    else:
        output_text(
            [dataclasses.asdict(o) for o in orders],
            columns=["id", "seller", "status", "totalCost", "waybill"],
        )
    return 0


def handle_orders_reorder(args, client: AllegroClient) -> int:
    raw = client.get_orders(offset=0, limit=50)
    all_orders = [
        _parse_order(myorder)
        for group in raw.get("orderGroups", [])
        for myorder in group.get("myorders", [])
    ]
    order = next((o for o in all_orders if o.id == args.order_id), None)
    if not order:
        output_error([make_error(
            f"Order {args.order_id} not found in recent 50 orders",
            code="OrderNotFoundException",
            userMessage=f"Order {args.order_id} was not found in recent orders.",
        )])
        return 1

    reorderable = [o for o in order.offers if "CAN_BUY_AGAIN" in o.traits]
    if not reorderable:
        output_error([make_error(
            f"No reorderable items in order {args.order_id}",
            code="CannotReorderException",
            userMessage=f"None of the items in order {args.order_id} can be reordered.",
        )])
        return 1

    for offer in reorderable:
        client.change_cart_quantity(offer.id, delta=offer.quantity, seller_id=order.sellerId)

    output_json({"reordered": len(reorderable), "orderId": order.id})
    return 0


def handle_orders_returns(args, client: AllegroClient) -> int:
    args.status = "RETURNED"
    return handle_orders_list(args, client)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_orders.py -k "handle_orders" -v
```
Expected: all 8 tests PASS

- [ ] **Step 5: Run full suite**

```bash
pytest
```
Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add allegro_cli/commands/orders.py tests/test_orders.py
git commit -m "feat: add orders command handlers (list, reorder, returns)"
```

---

### Task 4: CLI wiring — parser + dispatch

**Files:**
- Modify: `allegro_cli/main.py`

**Interfaces:**
- Consumes: `handle_orders_list`, `handle_orders_reorder`, `handle_orders_returns` from `allegro_cli.commands.orders`
- Produces: `allegro orders list [--limit N] [--page N] [--status S] [--search T]`, `allegro orders reorder <order_id>`, `allegro orders returns [--limit N] [--page N]`

- [ ] **Step 1: Write failing parser tests**

Add to `tests/test_orders.py`:

```python
from allegro_cli.main import create_parser, main


def test_parser_orders_list():
    parser = create_parser()
    args = parser.parse_args(["orders", "list"])
    assert args.command == "orders"
    assert args.orders_action == "list"
    assert args.limit == 15
    assert args.page == 1
    assert args.search is None
    assert args.status is None


def test_parser_orders_list_with_filters():
    parser = create_parser()
    args = parser.parse_args([
        "orders", "list", "--limit", "30", "--page", "2",
        "--status", "SENT", "--search", "laptop",
    ])
    assert args.limit == 30
    assert args.page == 2
    assert args.status == "SENT"
    assert args.search == "laptop"


def test_parser_orders_reorder():
    parser = create_parser()
    args = parser.parse_args(["orders", "reorder", "order-abc-123"])
    assert args.command == "orders"
    assert args.orders_action == "reorder"
    assert args.order_id == "order-abc-123"


def test_parser_orders_returns():
    parser = create_parser()
    args = parser.parse_args(["orders", "returns"])
    assert args.command == "orders"
    assert args.orders_action == "returns"


def test_orders_list_command_end_to_end(capsys):
    """Integration: main() dispatches to orders list via mock client."""
    with (
        patch("allegro_cli.main.load_config") as mock_load,
        patch("allegro_cli.main.ensure_dirs"),
        patch("allegro_cli.api.client.AllegroClient", return_value=_make_mock_client()),
        patch("sys.argv", ["allegro", "orders", "list", "--format", "json"]),
    ):
        mock_load.return_value = MagicMock(
            cookies="session=x",
            edgeBaseUrl="https://edge.allegro.pl",
            outputFormat="text",
            cloakLicenseKey=None,
        )
        result = main()

    assert result == 0
    data = json.loads(capsys.readouterr().out)
    assert "orders" in data
    assert len(data["orders"]) == 3
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_orders.py -k "parser_orders or orders_list_command" -v
```
Expected: FAIL — argparse error, `orders` not a valid choice

- [ ] **Step 3: Add orders parser to `create_parser()` in `allegro_cli/main.py`**

After the `packages` parser block (before the `login` block), add:

```python
    # --- orders ---
    sp_orders = sub.add_parser("orders", parents=[common], help="View and manage past orders")
    orders_sub = sp_orders.add_subparsers(dest="orders_action", required=True)

    sp_orders_list = orders_sub.add_parser("list", parents=[common], help="List past orders")
    sp_orders_list.add_argument("--limit", type=int, default=15, help="Number of orders to fetch (default: 15)")
    sp_orders_list.add_argument("--page", type=int, default=1, help="Page number (default: 1)")
    sp_orders_list.add_argument("--status", default=None, help="Filter by status: SENT, DELIVERED, RETURNED, etc.")
    sp_orders_list.add_argument("--search", default=None, help="Search by offer title (case-insensitive)")

    sp_orders_reorder = orders_sub.add_parser("reorder", parents=[common], help="Reorder items from a past order")
    sp_orders_reorder.add_argument("order_id", help="Order ID to reorder")

    sp_orders_returns = orders_sub.add_parser("returns", parents=[common], help="List orders with return/transit status")
    sp_orders_returns.add_argument("--limit", type=int, default=15, help="Number of orders to fetch (default: 15)")
    sp_orders_returns.add_argument("--page", type=int, default=1, help="Page number (default: 1)")
```

- [ ] **Step 4: Add orders dispatch to `main()` in `allegro_cli/main.py`**

Inside the `match args.command:` block, after the `"packages"` case, add:

```python
                case "orders":
                    from allegro_cli.commands.orders import (
                        handle_orders_list,
                        handle_orders_reorder,
                        handle_orders_returns,
                    )
                    match args.orders_action:
                        case "list":
                            return handle_orders_list(args, client)
                        case "reorder":
                            return handle_orders_reorder(args, client)
                        case "returns":
                            return handle_orders_returns(args, client)
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_orders.py -k "parser_orders or orders_list_command" -v
```
Expected: all 5 tests PASS

- [ ] **Step 6: Run full suite**

```bash
pytest
```
Expected: all tests PASS

- [ ] **Step 7: Commit**

```bash
git add allegro_cli/main.py tests/test_orders.py
git commit -m "feat: wire orders subcommand into CLI parser and dispatch"
```

---

### Task 5: Tool schemas

**Files:**
- Modify: `agent_specs/tools.json`

**Interfaces:**
- Produces: `allegro_orders_list`, `allegro_orders_reorder`, `allegro_orders_returns` tool definitions

- [ ] **Step 1: Add three tool definitions to `agent_specs/tools.json`**

Add after the `allegro_track_packages` entry (before the closing `]`):

```json
  {
    "name": "allegro_orders_list",
    "description": "List past Allegro orders with status, price, and tracking info. Supports filtering by status and title search.",
    "parameters": {
      "type": "object",
      "properties": {
        "limit": { "type": "integer", "description": "Number of orders to fetch (default: 15, max: 50)", "default": 15 },
        "page": { "type": "integer", "description": "Page number (default: 1)", "default": 1 },
        "status": { "type": "string", "enum": ["SENT", "DELIVERED", "RETURNED", "RETURN_IN_PROGRESS"], "description": "Filter by order status" },
        "search": { "type": "string", "description": "Filter by offer title (case-insensitive substring)" },
        "compact": { "type": "boolean", "description": "Return minimal fields for token efficiency", "default": false }
      },
      "required": []
    }
  },
  {
    "name": "allegro_orders_reorder",
    "description": "Re-add all reorderable items from a past order to the shopping cart. Only items with CAN_BUY_AGAIN trait are added.",
    "parameters": {
      "type": "object",
      "properties": {
        "order_id": { "type": "string", "description": "The order ID to reorder (from allegro_orders_list)" }
      },
      "required": ["order_id"]
    }
  },
  {
    "name": "allegro_orders_returns",
    "description": "List orders currently in return or transit-return status (RETURNED, RETURN_IN_PROGRESS).",
    "parameters": {
      "type": "object",
      "properties": {
        "limit": { "type": "integer", "description": "Number of orders to fetch (default: 15)", "default": 15 },
        "page": { "type": "integer", "description": "Page number (default: 1)", "default": 1 }
      },
      "required": []
    }
  }
```

- [ ] **Step 2: Validate JSON is well-formed**

```bash
python3 -c "import json; json.load(open('agent_specs/tools.json')); print('valid')"
```
Expected: `valid`

- [ ] **Step 3: Run full suite**

```bash
pytest
```
Expected: all tests PASS

- [ ] **Step 4: Commit**

```bash
git add agent_specs/tools.json
git commit -m "feat: add orders tool schemas to agent_specs/tools.json"
```
