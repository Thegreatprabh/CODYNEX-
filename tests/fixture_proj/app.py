"""Fixture: app — entry point, depends on service + utils."""
from service import create_user, checkout
from utils import money


def main():
    user = create_user("Ada", "ada@example.com")
    order, receipt = checkout(user, 42.5)
    print("receipt:", receipt)
    print("refund would be:", money(order.total))


if __name__ == "__main__":
    main()
