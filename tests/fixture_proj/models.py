"""Fixture: models — data containers, no dependencies."""
from dataclasses import dataclass


@dataclass
class User:
    name: str
    email: str


@dataclass
class Order:
    order_id: int
    user: User
    total: float
