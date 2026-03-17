import re

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
_TAG_RE = re.compile(r"<[^>]+>")
_PIN_RE = re.compile(r"^\d{1,6}$")


def clean(value, max_length=200):
    """Ensure value is a plain string, strip HTML tags, limit length."""
    if not isinstance(value, str):
        return ""
    value = _TAG_RE.sub("", value)
    return value.strip()[:max_length]


def valid_uuid(value):
    """Return value if valid UUID string, else None."""
    if isinstance(value, str) and _UUID_RE.match(value):
        return value
    return None


def valid_email(value):
    """Return cleaned email if valid, else empty string."""
    if not isinstance(value, str):
        return ""
    value = value.strip()[:254]
    if _EMAIL_RE.match(value):
        return value
    return ""


def valid_int(value, min_val=None, max_val=None, default=0):
    """Parse integer with optional bounds."""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    if min_val is not None and n < min_val:
        return default
    if max_val is not None and n > max_val:
        return default
    return n


def valid_float(value, min_val=0.0, default=0.0):
    """Parse float with minimum."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    if f < min_val:
        return default
    return f


def valid_pin(value):
    """Return stripped PIN if numeric and up to 6 digits, else empty string."""
    if not isinstance(value, str):
        return ""
    value = value.strip()
    if _PIN_RE.match(value):
        return value
    return ""
