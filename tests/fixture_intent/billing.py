"""Billing engine — invoices, refunds, and receipts."""
from ledger import record


def invoice(customer, amount):
    """Create an invoice for a customer."""
    return record(customer, amount, kind="invoice")


def refund(customer, amount):
    """Refund a previous invoice."""
    return record(customer, -amount, kind="refund")
