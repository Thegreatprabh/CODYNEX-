"""DNA config: resolve the active project slug."""

import os

from .model import store as store_mod


def resolve_project(explicit=None):
    """Return (slug, error). Explicit slug wins, else .dna marker walk-up."""
    if explicit:
        return store_mod.slugify(explicit), None
    slug = store_mod.find_slug()
    if slug:
        return slug, None
    return None, ("no DNA project found here — run `dna init [path]` first "
                  f"(cwd: {os.getcwd()})")
