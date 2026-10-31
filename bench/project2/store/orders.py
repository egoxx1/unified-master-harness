from .config import TIER_DISCOUNTS
from .pricing import apply_discount


def line_total(catalog, sku, qty):
    """Cents for qty units of sku."""
    return catalog[sku]["price"] * qty


def order_total(catalog, lines, tier=None):
    """Total in cents for [(sku, qty), ...]; members get their tier discount."""
    subtotal = sum(line_total(catalog, sku, qty) for sku, qty in lines)
    if tier:
        subtotal = apply_discount(subtotal, TIER_DISCOUNTS[tier])
    return subtotal
