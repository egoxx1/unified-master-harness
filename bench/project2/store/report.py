from .money import format_cents
from .orders import order_total


def daily_report(catalog, orders):
    """One line per order ("order <id>: $x.yy") and a final total, for [(id, lines, tier), ...]."""
    out, grand = [], 0
    for order_id, lines, tier in orders:
        cents = order_total(catalog, lines, tier)
        grand += cents
        out.append(f"order {order_id}: {format_cents(cents)}")
    out.append(f"total: {format_cents(grand)}")
    return out
