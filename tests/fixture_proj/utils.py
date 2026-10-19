"""Fixture: utils — helpers, no dependencies."""


def slugify(text):
    """Make a url-safe slug."""
    return text.lower().replace(" ", "-")


def money(amount):
    """Format a float as currency."""
    return f"${amount:.2f}"
