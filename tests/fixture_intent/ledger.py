"""Double-entry ledger for the fixture shop."""


def record(customer, amount, kind="entry"):
    """Record one ledger entry."""
    return {"customer": customer, "amount": amount, "kind": kind}
