import json
import sys
from io import StringIO
from unittest.mock import MagicMock

from allegro_cli.api.models import Order, OrderOffer, OrderNotFoundException, CannotReorderException
from allegro_cli.api.mock_client import MockAllegroClient
from allegro_cli.config import Config
from allegro_cli.commands.orders import handle_orders_list, handle_orders_reorder, handle_orders_returns


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
