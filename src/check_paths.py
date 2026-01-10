#from __future__ import annotations

import os
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

#from fastapi import FastAPI, Form, Request
#from fastapi.responses import HTMLResponse
#from fastapi.staticfiles import StaticFiles
#from fastapi.templating import Jinja2Templates
#from markupsafe import Markup, escape

#from google.cloud import storage

#from src.config import settings
#from src.documents import list_documents
#from src.rag import rag_answer


# --- Paths (project-root based) ---
ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = ROOT / "templates"
STATIC_DIR = ROOT / "static"

print("MAIN FILE:", __file__)
print("ROOT:", ROOT)
print("TEMPLATES_DIR:", TEMPLATES_DIR, "exists:", TEMPLATES_DIR.exists())
print("STATIC_DIR:", STATIC_DIR, "exists:", STATIC_DIR.exists())

