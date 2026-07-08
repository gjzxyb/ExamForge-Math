"""Entrypoint for uvicorn --app-dir src."""
from pathlib import Path

from examforge.web import create_app

app = create_app(Path("data"))