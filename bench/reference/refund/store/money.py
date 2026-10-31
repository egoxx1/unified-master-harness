def to_cents(amount):
    """Parse a price such as "19.99" or "-5.10" (credits are negative) into integer cents."""
    return round(float(amount) * 100)


def format_cents(cents):
    """Format integer cents as a price, e.g. 1999 -> "$19.99"."""
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}${cents // 100}.{cents % 100:02d}"
