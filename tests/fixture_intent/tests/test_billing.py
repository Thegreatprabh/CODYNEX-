"""Fixture tests — billing behaviours the author pinned down."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from billing import invoice, refund


def test_invoice_total():
    inv = invoice("Ada", 42.5)
    assert inv["amount"] == 42.5
    assert inv["kind"] == "invoice"


def test_invoice_refund():
    inv = invoice("Bob", 10.0)
    r = refund("Bob", 10.0)
    assert r["amount"] == -inv["amount"]
