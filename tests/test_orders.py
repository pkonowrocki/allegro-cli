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
