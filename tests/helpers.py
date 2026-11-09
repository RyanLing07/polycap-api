from app.load_csv import COLUMNS


def jan(first_12_digits: str) -> str:
    """Add the correct check digit to 12 digits, giving a valid 13-digit JAN code."""
    digits = [int(c) for c in first_12_digits]
    total = sum(d * (3 if i % 2 else 1) for i, d in enumerate(digits))
    return first_12_digits + str((10 - total % 10) % 10)


def row(**values):
    """A CSV row as the loader sees it: every column present, empty ones None."""
    result = {column: None for column in COLUMNS}
    result.update(values)
    return result
