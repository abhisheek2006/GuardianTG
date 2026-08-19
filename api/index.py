"""Vercel serverless entry point.

Vercel detects the FastAPI instance named ``app`` exported from this file
(``api/index.py``) and wraps it as a serverless function. All routes are
rewritten to this entrypoint by ``vercel.json``.
"""

from app.web.main import app

__all__ = ["app"]