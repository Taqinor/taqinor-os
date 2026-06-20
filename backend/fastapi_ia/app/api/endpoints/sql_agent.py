from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.security import get_raw_token, verify_token
from app.services.action_tools import ActionContext
from app.services.sql_agent_service import sql_agent_service

router = APIRouter()


def _require_company_id(token_payload: dict) -> int:
    """ERR44 — Extrait un company_id PRESENT et NON NUL du JWT, sinon refuse.

    Le scoping par societe est la frontiere de securite de l'agent SQL : un jeton
    sans claim `company_id` (ou avec company_id=0) desactiverait tout le filtrage
    tenant et lirait toutes les societes. On refuse comme le fait l'OCR (403)."""
    company_id = token_payload.get("company_id")
    try:
        company_id = int(company_id) if company_id is not None else 0
    except (TypeError, ValueError):
        company_id = 0
    if not company_id:
        raise HTTPException(
            status_code=403,
            detail="Aucune entreprise associée à votre compte.",
        )
    return company_id


class SQLQuery(BaseModel):
    question: str


class SQLResponse(BaseModel):
    answer: str
    # ERR84 — Le SQL genere (avec les vrais noms de tables) n'est jamais
    # divulgue au client (divulgation de schema). Le champ reste present pour
    # ne pas casser le contrat frontend, mais il est TOUJOURS vide cote reponse.
    sql_query: str = ""
    data: list | None = None
    # N86 — True si l'agent a effectue une action d'ecriture (ticket SAV,
    # brouillon de bon de commande, visite). Le frontend affiche un badge.
    action_performed: bool = False


class HistoryMessage(BaseModel):
    role: str
    content: str


@router.post("/query", response_model=SQLResponse)
async def query_database(
    request: SQLQuery,
    token_payload: dict = Depends(verify_token),
    raw_token: str = Depends(get_raw_token),
):
    """Agent SQL conversationnel — repond aux questions en francais.

    N86 — l'agent peut aussi effectuer des ACTIONS d'ecriture (ticket SAV,
    brouillon de bon de commande, planification de visite) quand l'appelant a
    le droit d'ecriture. Le contexte d'action porte le role/les permissions du
    JWT + le jeton brut (relaye a l'API Django interne, qui tranche).
    """
    user_id = int(token_payload.get("user_id", 0))
    # ERR44 — exige un company_id present et non nul (403 sinon).
    company_id = _require_company_id(token_payload)

    action_ctx = ActionContext(
        company_id=company_id,
        role=token_payload.get("role", ""),
        permissions=token_payload.get("permissions") or [],
        token=raw_token,
        is_superuser=bool(token_payload.get("is_superuser", False)),
    )

    result = await sql_agent_service.query(
        question=request.question,
        user_id=user_id,
        company_id=company_id,
        action_ctx=action_ctx,
    )
    return SQLResponse(
        answer=result["answer"],
        # ERR84 — jamais le SQL brut : redige cote serveur.
        sql_query="",
        data=result["data"],
        action_performed=bool(result.get("action_performed", False)),
    )


@router.get("/history", response_model=list[HistoryMessage])
def get_history(token_payload: dict = Depends(verify_token)):
    """Retourne l'historique de conversation (24h, 20 messages max)."""
    user_id = int(token_payload.get("user_id", 0))
    return sql_agent_service.get_history(user_id)


@router.delete("/history", status_code=204)
def clear_history(token_payload: dict = Depends(verify_token)):
    """Efface la conversation de l'utilisateur."""
    user_id = int(token_payload.get("user_id", 0))
    sql_agent_service.clear_history(user_id)


@router.get("/schema")
async def get_schema(token_payload: dict = Depends(verify_token)):
    """Retourne les tables disponibles et le provider LLM actif."""
    return await sql_agent_service.get_schema_summary()
