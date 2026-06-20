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

# Agent — outils d'ACTION (N86). URL interne du backend Django pour relayer les
# ecritures (ouverture de ticket SAV, brouillon de bon de commande, planif. de
# visite) via l'API REST/ORM — JAMAIS de SQL d'ecriture (CLAUDE.md regle #1).
# Vide => outils d'action non exposes (degradation gracieuse). Defaut docker :
# le service Django interne ecoute sur http://django_core:8000.
DJANGO_INTERNAL_URL = os.environ.get(
    "DJANGO_INTERNAL_URL", "http://django_core:8000")

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
# Connexion owner — utilisee pour les operations administrees du service OCR
# (create/upgrade de ia_ocr_document, voir core/database.py). NE doit PAS servir
# a l'agent NL->SQL : il a sa propre connexion lecture seule ci-dessous.
DATABASE_URL = (
    f"postgresql://{DB_USER}:{_pw}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# ERR3 — Connexion DEDIEE LECTURE SEULE pour l'agent NL->SQL.
# L'agent ne doit jamais se connecter avec le role owner (qui a INSERT/UPDATE/
# DELETE/DDL). Si SQL_AGENT_DB_USER est defini en .env (un role Postgres ne
# disposant QUE de SELECT sur les tables de l'allowlist, cf. docker-compose.yml),
# l'agent l'utilise ; sinon il retombe SANS RIEN CASSER sur DATABASE_URL.
# Defense en profondeur : ce role read-only complete le garde single-SELECT et
# l'injection company_id du service — meme une requete d'ecriture qui passerait
# entre les mailles est refusee par Postgres faute de privileges.
SQL_AGENT_DB_USER = os.environ.get("SQL_AGENT_DB_USER", "")
SQL_AGENT_DB_PASSWORD = os.environ.get("SQL_AGENT_DB_PASSWORD", "")

if SQL_AGENT_DB_USER:
    _agent_pw = quote_plus(SQL_AGENT_DB_PASSWORD)
    SQL_AGENT_DATABASE_URL = (
        f"postgresql://{SQL_AGENT_DB_USER}:{_agent_pw}"
        f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
else:
    SQL_AGENT_DATABASE_URL = DATABASE_URL
