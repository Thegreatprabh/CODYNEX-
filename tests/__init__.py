"""Shared fixtures + ignore the sample project's own tests."""
import os

collect_ignore = ["fixture_proj", "fixture_intent"]

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "fixture_proj")
