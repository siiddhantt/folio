def normalized_title(value):
    """Return a short title that PostgreSQL text can store, or no usable title."""
    if not isinstance(value, str) or "\x00" in value:
        return None
    try:
        value.encode("utf-8")
    except UnicodeError:
        return None
    title = " ".join(value.split())
    return title if 1 <= len(title) <= 60 else None
