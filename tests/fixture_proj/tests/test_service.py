"""Fixture tests — one passing test for service.checkout."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from service import create_user, checkout


def test_checkout_receipt():
    user = create_user("Ada", "ada@example.com")
    order, receipt = checkout(user, 42.5)
    assert order.total == 42.5
    assert receipt == "ada-$42.50"


def test_create_user():
    user = create_user("Bob", "bob@example.com")
    assert user.name == "Bob"
