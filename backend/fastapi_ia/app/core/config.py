import os
from urllib.parse import quote_plus

# FastAPI configuration
_DEBUG = os.environ.get("DJANGO_DEBUG", "True").lower() in ("true", "1", "yes")
FASTAPI_SECRET_KEY = os.environ.get("FASTAPI_SECRET_KEY", "change-me" if _DEBUG else "")

if not _DEBUG and (not FASTAPI_SECRET_KEY or FASTAPI_SECRET_KEY == "change-me"):
    raise RuntimeError(
        "La variable d'environnement FASTAPI_SECRET_KEY est obligatoire en production."
    )

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY", "")
ZHIPU_API_KEY = os.environ.get("ZHIPU_API_KEY", "")

# Database
DB_NAME = os.environ.get("DB_NAME", "erp_db")
DB_USER = os.environ.get("DB_USER", "erp_user")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "erp_password")
DB_HOST = os.environ.get("DB_HOST", "db")
DB_PORT = os.environ.get("DB_PORT", "5432")

_pw = quote_plus(DB_PASSWORD)
DATABASE_URL = (
    f"postgresql://{DB_USER}:{_pw}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)
