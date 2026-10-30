from datetime import date


def parse(text):
    """'2026-01-03' -> date(2026, 1, 3)"""
    y, m, d = (int(p) for p in text.split("-"))
    return date(y, m, d)


def days_between(start, end):
    """Number of calendar days from start to end, counting both ends."""
    return (end - start).days
