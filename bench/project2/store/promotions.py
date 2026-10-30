import json
from pathlib import Path

from .pricing import apply_discount

PROMOTIONS = Path(__file__).resolve().parent.parent / "data" / "promotions.json"


def load_promotions(path=PROMOTIONS):
    with open(path) as f:
        return {p["code"]: p for p in json.load(f)}


def promo_price(cents, code, promotions=None):
    """Price in cents after applying a promotion code."""
    promotions = promotions if promotions is not None else load_promotions()
    return apply_discount(cents, promotions[code]["rate"])
