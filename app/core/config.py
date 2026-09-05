# app/core/config.py

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent.parent / ".env")

# Railway injects a plain "postgresql://" URL; SQLAlchemy's async engine
# needs the asyncpg dialect spelled out explicitly.
DATABASE_URL = os.getenv("DATABASE_URL", "").replace(
    "postgresql://", "postgresql+asyncpg://", 1
)

JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ALGORITHM = "HS256"
# 7 days — a personal single-user app doesn't need short-lived tokens with
# refresh-token complexity.
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "10080"))

ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]

TECTONIC_TIMEOUT_SECONDS = int(os.getenv("TECTONIC_TIMEOUT_SECONDS", "45"))

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
