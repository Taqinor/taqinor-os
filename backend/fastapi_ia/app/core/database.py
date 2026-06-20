import logging
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.core.config import DATABASE_URL

logger = logging.getLogger(__name__)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


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
