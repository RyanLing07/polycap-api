import re

_SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def slugify(text: str) -> str:
    """"RX-78-2 Gundam" -> "rx-78-2-gundam"."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def is_valid_slug(text: str) -> bool:
    return bool(_SLUG_RE.match(text))
