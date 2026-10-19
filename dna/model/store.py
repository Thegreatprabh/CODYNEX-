"""Persistence: JSON store at ~/.dna/<project-slug>/dna.json (dir 0700)."""

import json
import os
import re

from .dna import ProjectDNA

BASE = os.path.expanduser("~/.dna")


def slugify(name):
    """Filesystem-safe project slug."""
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", name.strip().lower()).strip("-")
    return slug or "project"


def project_dir(slug):
    return os.path.join(BASE, slug)


def save(dna):
    """Save DNA to ~/.dna/<slug>/dna.json. Creates dir 0700."""
    d = project_dir(dna.project)
    os.makedirs(d, mode=0o700, exist_ok=True)
    # enforce 0700 even if dir already existed
    try:
        os.chmod(d, 0o700)
    except OSError:
        pass
    path = os.path.join(d, "dna.json")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(dna.to_dict(), f, indent=2)
    os.replace(tmp, path)
    return path


def load(slug):
    """Load DNA by slug. Returns ProjectDNA or None."""
    path = os.path.join(project_dir(slug), "dna.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return ProjectDNA.from_dict(json.load(f))


def list_projects():
    """Return sorted list of saved project slugs."""
    if not os.path.isdir(BASE):
        return []
    return sorted(d for d in os.listdir(BASE)
                  if os.path.isdir(os.path.join(BASE, d)))


MARKER = ".dna"


def mark_project(root, slug):
    """Write the project marker so CLI commands can find the DNA."""
    d = os.path.join(root, MARKER)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "slug"), "w", encoding="utf-8") as f:
        f.write(slug)
    return d


def find_slug(start=None):
    """Walk up from start (default cwd) looking for a .dna marker."""
    cur = os.path.abspath(start or os.getcwd())
    while True:
        marker = os.path.join(cur, MARKER, "slug")
        if os.path.isfile(marker):
            with open(marker, "r", encoding="utf-8") as f:
                return f.read().strip()
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent
