import logging
import os
import time
import uuid

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.core.config import DATABASE_URL, SQL_AGENT_DATABASE_URL

logger = logging.getLogger(__name__)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ── AANA5 — moteur DEDIE de l'agent NL->SQL, borne dans le temps ─────────────
# Une requete ecrite par le LLM (jointure explosive, `pg_sleep` passe en amont)
# ne doit jamais tenir une connexion indefiniment : chaque connexion du moteur
# de l'agent porte `statement_timeout = 15 s` (Postgres annule la requete).
SQL_AGENT_STATEMENT_TIMEOUT_MS = 15000


def sql_agent_engine_args() -> dict:
    """Arguments du moteur SQLAlchemy de l'agent (timeout pose a la connexion
    par libpq, donc impossible a oublier requete par requete)."""
    return {
        "pool_pre_ping": True,
        "connect_args": {
            "options": f"-c statement_timeout={SQL_AGENT_STATEMENT_TIMEOUT_MS}",
        },
    }


def create_sql_agent_engine():
    """Moteur de l'agent NL->SQL (role dedie lecture seule SQL_AGENT_DB_USER)
    avec le statement_timeout. SEUL point de creation de ce moteur."""
    return create_engine(SQL_AGENT_DATABASE_URL, **sql_agent_engine_args())


# ── AANA5 — limiteur de debit partage (Redis, fenetre glissante) ─────────────
# FAIL CLOSED (ERR86, comme l'OCR) : Redis injoignable => 503, jamais un
# plafond silencieusement desactive (appels LLM payants illimites / DoS).
_RATE_LIMIT_REDIS_URL = os.environ.get("REDIS_URL") or "redis://{}:{}/1".format(
    os.environ.get("REDIS_HOST", "redis"), os.environ.get("REDIS_PORT", "6379"))
_rate_limit_redis = None


def get_rate_limit_redis():
    global _rate_limit_redis
    if _rate_limit_redis is None:
        import redis
        _rate_limit_redis = redis.from_url(
            _RATE_LIMIT_REDIS_URL, decode_responses=True)
    return _rate_limit_redis


def check_rate_limit(bucket: str, user_id, max_requests: int,
                     window_seconds: int, detail: str) -> None:
    """Fenetre glissante par (bucket, utilisateur) : 429 au-dela de
    `max_requests` sur `window_seconds`, 503 si Redis est injoignable."""
    try:
        r = get_rate_limit_redis()
        key = f"{bucket}:{user_id}"
        now = time.time()
        pipe = r.pipeline()
        pipe.zremrangebyscore(key, 0, now - window_seconds)
        # Membre UNIQUE : deux requetes a la meme horloge comptent deux fois.
        pipe.zadd(key, {f"{now}:{uuid.uuid4().hex}": now})
        pipe.zcard(key)
        pipe.expire(key, window_seconds)
        count = pipe.execute()[2]
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=503,
            detail=(
                "Service de limitation temporairement indisponible. "
                "Réessayez dans quelques instants."
            ),
        )
    if count > max_requests:
        raise HTTPException(status_code=429, detail=detail)


def _ddl_enabled() -> bool:
    """ERR85 — Les operations DDL (CREATE/ALTER/INDEX) ne s'executent QUE si elles
    sont explicitement activees via RUN_DB_DDL (defaut OFF). Sinon le service
    demarre sans toucher au schema avec le role owner a chaque boot — la
    migration est un acte explicite/ponctuel, pas un effet de bord de demarrage."""
    return os.environ.get("RUN_DB_DDL", "").lower() in ("1", "true", "yes")


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables() -> None:
    """ERR85 — N'execute du DDL (CREATE TABLE / ALTER / CREATE INDEX) avec le role
    owner QUE si RUN_DB_DDL est explicitement active. Par defaut (OFF) la fonction
    ne fait RIEN : le service ne reapplique pas de migration ad-hoc en owner a
    chaque demarrage. Le DDL reste idempotent (IF NOT EXISTS) lorsqu'il s'execute."""
    if not _ddl_enabled():
        logger.info(
            "create_tables: DDL desactive (RUN_DB_DDL non defini) — aucune "
            "operation de schema au demarrage."
        )
        return

    from sqlalchemy import text
    from app.models import ocr  # noqa: F401 — registers the model

    Base.metadata.create_all(bind=engine)

    # In-place schema upgrades for tables owned by this service. Idempotent —
    # safe to run when explicitly enabled. Real migration framework can come later.
    with engine.begin() as conn:
        conn.execute(text(
            "ALTER TABLE ia_ocr_document "
            "ADD COLUMN IF NOT EXISTS company_id BIGINT"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_ia_ocr_document_company_id "
            "ON ia_ocr_document (company_id)"
        ))
