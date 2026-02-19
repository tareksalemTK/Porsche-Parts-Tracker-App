import os
from pathlib import Path

# Base Directory (Root of the project)
# app/config.py -> app/ -> root/
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
ASSETS_DIR = BASE_DIR / "assets"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
ASSETS_DIR.mkdir(exist_ok=True)

# Environment: 'dev' (default) or 'prod'
ENV = os.getenv("APP_ENV", "dev")

if ENV == "prod":
    DB_NAME = "porsche_parts_prod.db"
    DEBUG = False
else:
    DB_NAME = "porsche_parts.db" # Keep existing name for dev
    DEBUG = True

DB_PATH = DATA_DIR / DB_NAME


