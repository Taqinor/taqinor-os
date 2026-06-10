import os
import time

import redis
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import verify_token
from app.models.ocr import OcrDocument
from app.services.ocr_service import ocr_service

router = APIRouter()

# ── Constantes de sécurité ────────────────────────────────────────────────────
MAX_FILE_SIZE = 10 * 1024 * 1024   # 10 Mo
RATE_LIMIT_MAX = 20                 # requêtes max
RATE_LIMIT_WINDOW = 3600            # par heure (en secondes)

ACCEPTED_CONTENT_TYPES = (
    "image/jpeg", "image/png", "image/tiff", "image/webp", "application/pdf"
)

MAGIC_BYTES: dict[str, list[bytes]] = {
    "image/jpeg":        [b"\xff\xd8\xff"],
    "image/png":         [b"\x89PNG\r\n\x1a\n"],
    "image/tiff":        [b"II*\x00", b"MM\x00*"],
    "image/webp":        [b"RIFF"],
    "application/pdf":   [b"%PDF-"],
}

_REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/1")
_redis_client: redis.Redis | None = None


def _get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(_REDIS_URL, decode_responses=True)
    return _redis_client


def _check_magic_bytes(content_type: str, data: bytes) -> bool:
    signatures = MAGIC_BYTES.get(content_type, [])
    for sig in signatures:
        if data[:len(sig)] == sig:
            if content_type == "image/webp":
                return data[8:12] == b"WEBP"
            return True
    return False


def _check_rate_limit(user_id: str) -> None:
    try:
        r = _get_redis()
        key = f"ocr_rate:{user_id}"
        now = time.time()
        window_start = now - RATE_LIMIT_WINDOW

        pipe = r.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zadd(key, {str(now): now})
        pipe.zcard(key)
        pipe.expire(key, RATE_LIMIT_WINDOW)
        results = pipe.execute()

        count = results[2]
        if count > RATE_LIMIT_MAX:
            raise HTTPException(
                status_code=429,
                detail=f"Limite atteinte : {RATE_LIMIT_MAX} analyses OCR par heure. Réessayez plus tard.",
            )
    except HTTPException:
        raise
    except Exception:
        pass


# ── Schémas ───────────────────────────────────────────────────────────────────

class OCRResult(BaseModel):
    texte_brut: str
    confiance: float
    blocs: list
    type_document: str = "autre"
    donnees_structurees: dict


class SaveDocumentRequest(BaseModel):
    filename: str
    texte_brut: str
    type_document: str = "autre"
    confiance: float = 0.0
    donnees_structurees: dict = {}


class SaveDocumentResponse(BaseModel):
    id: int
    message: str


class OcrDocumentItem(BaseModel):
    id: int
    filename: str
    type_document: str
    confiance: float
    username: str
    created_at: str
    donnees_structurees: dict


class StockLigne(BaseModel):
    reference: str | None = None
    nom: str = ""
    categorie_suggeree: str | None = None
    quantite: int = 1
    prix_unitaire_ht: float | None = None
    tva: float | None = None


class StockOcrResult(BaseModel):
    type_document: str = "autre"
    mouvement_suggere: str = "entree"
    fournisseur: str | None = None
    reference_document: str | None = None
    date: str | None = None
    confiance: float = 0.0
    lignes: list[StockLigne] = []
    texte_brut: str = ""


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/process_stock_document", response_model=StockOcrResult)
async def process_stock_document(
    file: UploadFile = File(...),
    doc_type: str = Form(""),
    token_payload: dict = Depends(verify_token),
):
    """Analyse OCR orientée stock — bon de livraison ou facture fournisseur."""
    user_id = str(
        token_payload.get("user_id", token_payload.get("sub", "anonymous"))
    )
    _check_rate_limit(user_id)

    if not file.content_type or file.content_type not in ACCEPTED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Type non accepté : '{file.content_type}'.",
        )

    contents = await file.read(MAX_FILE_SIZE + 1)
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="Fichier trop volumineux (max 10 Mo).",
        )

    if not _check_magic_bytes(file.content_type, contents):
        raise HTTPException(
            status_code=400,
            detail="Contenu du fichier invalide.",
        )

    result = await ocr_service.process_stock_document(
        contents,
        filename=file.filename or "",
        content_type=file.content_type,
        doc_type=doc_type,
    )
    return StockOcrResult(**result)


@router.post("/process_document", response_model=OCRResult)
async def process_document(
    file: UploadFile = File(...),
    token_payload: dict = Depends(verify_token),
):
    """
    Traitement OCR sécurisé d'une image ou d'un PDF.
    Protections : JWT, limite 10 Mo, validation Content-Type + magic bytes, rate limit 20/h.
    """
    user_id = str(token_payload.get("user_id", token_payload.get("sub", "anonymous")))
    _check_rate_limit(user_id)

    if not file.content_type or file.content_type not in ACCEPTED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Type de fichier non accepté : '{file.content_type}'. "
                f"Formats acceptés : {', '.join(ACCEPTED_CONTENT_TYPES)}"
            ),
        )

    contents = await file.read(MAX_FILE_SIZE + 1)
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="Fichier trop volumineux. Taille maximale autorisée : 10 Mo.",
        )

    if not _check_magic_bytes(file.content_type, contents):
        raise HTTPException(
            status_code=400,
            detail=(
                "Le contenu du fichier ne correspond pas au type déclaré. "
                "Fichier potentiellement malveillant rejeté."
            ),
        )

    if file.content_type == "application/pdf":
        result = await ocr_service.process_pdf(contents)
        # "texte_complet" on success, "texte_brut" on error path
        texte = result.get("texte_complet") or result.get("texte_brut", "")
        donnees = result.get("donnees_structurees", {})
        if not donnees and result.get("nb_pages"):
            donnees = {"nb_pages": result["nb_pages"]}
        return OCRResult(
            texte_brut=texte,
            confiance=float(result.get("confiance", 0.0)),
            blocs=[],
            type_document=result.get("type_document", "autre"),
            donnees_structurees=donnees,
        )

    result = await ocr_service.process_image(contents, filename=file.filename or "")
    return OCRResult(
        texte_brut=result.get("texte_brut", ""),
        confiance=float(result.get("confiance", 0.0)),
        blocs=result.get("blocs", []),
        type_document=result.get("type_document", "autre"),
        donnees_structurees=result.get("donnees_structurees", {}),
    )


def _require_company_id(token_payload: dict) -> int:
    """Extract company_id from the JWT or refuse the request.

    Tenant scoping is the security boundary — a token without a company_id
    must never read or write OCR documents.
    """
    company_id = token_payload.get("company_id")
    if not company_id:
        raise HTTPException(
            status_code=403,
            detail="Aucune entreprise associée à votre compte.",
        )
    return int(company_id)


@router.post("/save_document", response_model=SaveDocumentResponse)
def save_document(
    body: SaveDocumentRequest,
    token_payload: dict = Depends(verify_token),
    db: Session = Depends(get_db),
):
    """
    Enregistre un résultat OCR en base de données.
    Réservé aux utilisateurs avec le rôle responsable ou admin.
    """
    role = token_payload.get("role", "")
    if role not in ("responsable", "admin"):
        raise HTTPException(
            status_code=403,
            detail="Seuls les responsables et administrateurs peuvent enregistrer des documents OCR.",
        )

    company_id = _require_company_id(token_payload)
    user_id = int(token_payload.get("user_id", 0))
    username = token_payload.get("username", "")

    doc = OcrDocument(
        company_id=company_id,
        user_id=user_id,
        username=username,
        filename=body.filename,
        type_document=body.type_document,
        texte_brut=body.texte_brut,
        donnees_structurees=body.donnees_structurees,
        confiance=body.confiance,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    return SaveDocumentResponse(id=doc.id, message="Document enregistré avec succès.")


@router.get("/documents", response_model=list[OcrDocumentItem])
def list_documents(
    token_payload: dict = Depends(verify_token),
    db: Session = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
):
    """
    Liste les documents OCR sauvegardés.
    Toujours filtré par entreprise.
    - admin/responsable : voit tous les documents de leur entreprise
    - autre rôle        : voit uniquement ses propres documents
    """
    role = token_payload.get("role", "")
    user_id = int(token_payload.get("user_id", 0))
    company_id = _require_company_id(token_payload)

    query = db.query(OcrDocument).filter(OcrDocument.company_id == company_id)
    if role not in ("responsable", "admin"):
        query = query.filter(OcrDocument.user_id == user_id)

    docs = (
        query.order_by(OcrDocument.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return [
        OcrDocumentItem(
            id=d.id,
            filename=d.filename,
            type_document=d.type_document,
            confiance=d.confiance,
            username=d.username,
            created_at=d.created_at.isoformat(),
            donnees_structurees=d.donnees_structurees or {},
        )
        for d in docs
    ]


@router.delete("/documents/{doc_id}", status_code=204)
def delete_document(
    doc_id: int,
    token_payload: dict = Depends(verify_token),
    db: Session = Depends(get_db),
):
    """Supprime un document OCR — réservé admin/responsable, scope entreprise."""
    role = token_payload.get("role", "")
    if role not in ("responsable", "admin"):
        raise HTTPException(status_code=403, detail="Accès refusé.")

    company_id = _require_company_id(token_payload)
    doc = (
        db.query(OcrDocument)
        .filter(OcrDocument.id == doc_id, OcrDocument.company_id == company_id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document introuvable.")

    db.delete(doc)
    db.commit()
