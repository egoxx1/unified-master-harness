def apply_discount(cents, rate):
    """Price after a fractional discount (0.1 = 10% off), rounded to whole cents."""
    if not 0 <= rate <= 1:
        raise ValueError("rate must be between 0 and 1")
    return round(cents * (1 - rate))
