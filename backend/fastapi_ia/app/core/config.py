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

# Transcription audio (chat vocal) — Whisper auto-heberge via faster-whisper.
# OFF par defaut : quand desactive, l'endpoint /transcribe repond "disabled"
# (degradation gracieuse, pas une erreur) et le modele n'est JAMAIS telecharge
# (chargement paresseux au premier appel uniquement), donc le service demarre et
# le build CI passe sans poids ni reseau.
CHAT_TRANSCRIPTION_ENABLED = os.environ.get(
    "CHAT_TRANSCRIPTION_ENABLED", "0").lower() in ("true", "1", "yes")
# Taille du modele faster-whisper (small/medium multilingue conseille).
WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "small")
# Cache de telechargement des poids (persiste entre redemarrages du conteneur).
# Vide => cache HuggingFace par defaut (~/.cache/huggingface).
WHISPER_CACHE_DIR = os.environ.get("WHISPER_CACHE_DIR", "")
# Indice de langue (FR/AR/Darija). Vide => auto-detection complete.
# "ar" couvre la Darija marocaine ; sinon on laisse l'auto-detect actif.
WHISPER_LANGUAGE_HINT = os.environ.get("WHISPER_LANGUAGE_HINT", "")

# AG10 — Transcription vocale de l'ASSISTANT via Groq Whisper (API OpenAI-
# compatible). REUTILISE GROQ_API_KEY (deja requise pour l'agent SQL) — AUCUN
# nouveau service payant. Distinct du chemin self-heberge S10 ci-dessus : ce
# chemin sert le micro de l'assistant et appelle Groq en REST (whisper-large-v3),
# FR / AR / Darija. Cle absente => degradation gracieuse (message clair), aucun
# transcript persiste. Endpoint OpenAI-compatible audio/transcriptions de Groq.
GROQ_WHISPER_MODEL = os.environ.get("GROQ_WHISPER_MODEL", "whisper-large-v3")
GROQ_API_BASE_URL = os.environ.get(
    "GROQ_API_BASE_URL", "https://api.groq.com/openai/v1"
)
# Indice de langue facultatif pour Groq (FR/AR/Darija). Vide => auto-detection.
# "ar" couvre la Darija marocaine.
GROQ_WHISPER_LANGUAGE_HINT = os.environ.get("GROQ_WHISPER_LANGUAGE_HINT", "")

# Historique chat — Redis db 2 (db0=Celery, db1=Django cache)
_REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
_REDIS_PORT = os.environ.get("REDIS_PORT", "6379")
REDIS_CHAT_URL = f"redis://{_REDIS_HOST}:{_REDIS_PORT}/2"
CHAT_HISTORY_TTL = 86400   # 24h en secondes
CHAT_HISTORY_MAX = 20      # nb max de messages conserves

# AG2 — Propositions d'action en attente de confirmation (Redis db 2, meme
# instance que l'historique chat). Une action `outward`/`irreversible` n'est
# JAMAIS executee directement : l'agent renvoie une proposition signee (HMAC,
# inviolable) stockee sous un jeton avec un TTL court. L'endpoint /confirm la
# rejoue par jeton apres re-validation des entrees contre le catalogue.
REDIS_PROPOSAL_URL = f"redis://{_REDIS_HOST}:{_REDIS_PORT}/2"
# TTL court (5 min) : une proposition expiree doit etre re-demandee.
ACTION_PROPOSAL_TTL = int(os.environ.get("ACTION_PROPOSAL_TTL", "300"))
# Cle de signature des propositions. On reutilise la cle Django (deja partagee
# avec FastAPI pour le JWT) afin de ne PAS introduire de nouveau secret : la
# proposition est signee HMAC-SHA256 et verifiee avant tout rejouage.
ACTION_PROPOSAL_SECRET = (
    os.environ.get("ACTION_PROPOSAL_SECRET")
    or os.environ.get("DJANGO_SECRET_KEY", "")
    or FASTAPI_SECRET_KEY
)

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
