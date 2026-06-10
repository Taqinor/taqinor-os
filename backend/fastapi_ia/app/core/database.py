from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.core.config import DATABASE_URL

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables() -> None:
    from sqlalchemy import text
    from app.models import ocr  # noqa: F401 — registers the model

    Base.metadata.create_all(bind=engine)

    # In-place schema upgrades for tables owned by this service. Idempotent —
    # safe to run every startup. Real migration framework can come later.
    with engine.begin() as conn:
        conn.execute(text(
            "ALTER TABLE ia_ocr_document "
            "ADD COLUMN IF NOT EXISTS company_id BIGINT"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_ia_ocr_document_company_id "
            "ON ia_ocr_document (company_id)"
        ))
