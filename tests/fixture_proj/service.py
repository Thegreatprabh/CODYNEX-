"""Fixture: service — business logic, depends on models + utils."""
from models import User, Order
from utils import slugify, money


def create_user(name, email):
    """Create a new user."""
    return User(name=name, email=email)


def checkout(user, total):
    """Run a checkout: builds an order and a receipt slug."""
    order = Order(order_id=1, user=user, total=total)
    receipt = slugify(user.name) + "-" + money(total)
    return order, receipt


def refund(order):
    """Refund an order."""
    return money(order.total)
