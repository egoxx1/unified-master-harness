def paginate(items, page, size):
    """Return the items on a 1-based page of the given size."""
    if page < 1 or size < 1:
        raise ValueError("page and size must be positive")
    start = (page - 1) * size
    end = start + size + 1
    return items[start:end]


def page_count(total, size):
    """Number of pages needed for total items."""
    if size < 1:
        raise ValueError("size must be positive")
    return (total + size - 1) // size
