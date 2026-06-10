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

# Agent SQL — provider modifiable via .env sans changer le code
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
SQL_AGENT_PROVIDER = os.environ.get("SQL_AGENT_PROVIDER", "groq")
SQL_AGENT_MODEL = os.environ.get("SQL_AGENT_MODEL", "llama-3.3-70b-versatile")

# Historique chat — Redis db 2 (db0=Celery, db1=Django cache)
_REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
_REDIS_PORT = os.environ.get("REDIS_PORT", "6379")
REDIS_CHAT_URL = f"redis://{_REDIS_HOST}:{_REDIS_PORT}/2"
CHAT_HISTORY_TTL = 86400   # 24h en secondes
CHAT_HISTORY_MAX = 20      # nb max de messages conserves

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
