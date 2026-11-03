"""Business logic of the standard apps (plan v3, section 8). Importing this package registers the hooks."""

from app.apps import activities, billing, marketing, sales, service

__all__ = ["activities", "billing", "marketing", "sales", "service"]
