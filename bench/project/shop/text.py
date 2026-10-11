import re


def slugify(title):
    """Lowercase URL slug: letters and digits joined by single dashes."""
    title = title.strip().lower()
    return re.sub(r"[^a-z0-9]", "-", title).strip("-")


def truncate(text, limit):
    """Shorten text to at most limit characters, ending with '...' if cut."""
    if len(text) <= limit:
        return text
    return text[: max(limit - 3, 0)] + "..."
