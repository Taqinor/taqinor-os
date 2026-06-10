from datetime import datetime
from sqlalchemy import BigInteger, Column, DateTime, Float, String, Text, JSON
from app.core.database import Base


class OcrDocument(Base):
    __tablename__ = "ia_ocr_document"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    # Tenant scoping — every OCR document MUST be linked to a company.
    # nullable=True only to allow the ALTER TABLE on existing rows; new rows
    # are always written with a real company_id by the endpoints.
    company_id = Column(BigInteger, nullable=True, index=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    username = Column(String(150), nullable=False)
    filename = Column(String(255), nullable=False)
    type_document = Column(String(50), nullable=False, default="autre")
    texte_brut = Column(Text, nullable=False, default="")
    donnees_structurees = Column(JSON, nullable=False, default=dict)
    confiance = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
