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


def initials(name):
    """Initials with dots: 'Ada Lovelace' -> 'A.L.' (work in progress, hyphenated names next)."""
    return ".".join(part[0].upper() for part in name.split())
