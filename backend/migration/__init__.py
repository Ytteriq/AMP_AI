"""
backend/migration/__init__.py
Database migration utilities for multi-tenant data encryption.
"""

from backend.migration.migrate_ai_outputs import AIMigrationRunner

__all__ = ["AIMigrationRunner"]
