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

# Rate limits (see app/core/rate_limit.py). Login/signup are keyed by client
# IP since there's no account yet to key on; compile is keyed by user id
# since it's already authenticated and IP is a weaker signal (shared
# networks, proxies) for what's really a per-account resource cost (each
# call spawns a tectonic subprocess).
RATE_LIMIT_LOGIN_PER_MINUTE = int(os.getenv("RATE_LIMIT_LOGIN_PER_MINUTE", "10"))
RATE_LIMIT_SIGNUP_PER_HOUR = int(os.getenv("RATE_LIMIT_SIGNUP_PER_HOUR", "5"))
RATE_LIMIT_COMPILE_PER_MINUTE = int(os.getenv("RATE_LIMIT_COMPILE_PER_MINUTE", "6"))

# Documents are stored as a Postgres Text column (no DB-level cap), and
# pasted screenshots live inline as base64 data: URLs inside that same
# string (see README's known limitations) — without an application-level
# ceiling, one huge save would bloat the row indefinitely and slow every
# later compile. 10MB covers a genuinely long document with several
# pasted screenshots; anything past that is almost certainly accidental
# (e.g. a giant uncompressed paste).
MAX_DOCUMENT_CONTENT_BYTES = int(os.getenv("MAX_DOCUMENT_CONTENT_BYTES", str(10 * 1024 * 1024)))
