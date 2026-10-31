def apply_discount(cents, percent):
    """Price after a percentage discount (10 = 10% off), rounded to whole cents."""
    if not 0 <= percent <= 100:
        raise ValueError("percent must be between 0 and 100")
    return round(cents * (100 - percent) / 100)
