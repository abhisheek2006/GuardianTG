from __future__ import annotations

import os

from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.web.main import app

# Re-export the shared FastAPI app from app.web.main so imports stay clean.
__all__ = ["app", "templates"]


def mount_static() -> None:
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    if os.path.isdir(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")


mount_static()