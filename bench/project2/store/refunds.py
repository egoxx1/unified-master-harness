from .money import to_cents
from .orders import line_total


def refund_amount(catalog, sku, qty_returned, opened=False):
    """Cents to refund for returned units; opened items keep a 10% restocking fee (rounded down)."""
    amount = line_total(catalog, sku, qty_returned)
    if opened:
        amount -= amount // 10
    return amount


def manual_refund(amount):
    """Cents for an amount typed in by support staff, e.g. "12.30"."""
    return to_cents(amount)
