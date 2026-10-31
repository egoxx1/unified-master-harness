TAX_RATE = 0.1


def with_tax(price):
    """Price including tax, rounded to cents."""
    return round(price * (1 + TAX_RATE), 2)


def total(prices):
    """Sum of prices, rounded to cents."""
    return round(sum(prices), 2)
