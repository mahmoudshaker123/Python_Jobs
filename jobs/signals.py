"""Signals are intentionally empty.

Vercel does not run a persistent Celery worker. Email delivery is handled by the
protected scheduled endpoint so subscriptions and job imports remain fast and
retriable.
"""
