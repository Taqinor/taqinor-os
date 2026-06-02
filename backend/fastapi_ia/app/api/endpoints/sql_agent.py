from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.security import verify_token
from app.services.sql_agent_service import sql_agent_service

router = APIRouter()


class SQLQuery(BaseModel):
    question: str


class SQLResponse(BaseModel):
    answer: str
    sql_query: str
    data: list | None = None


class HistoryMessage(BaseModel):
    role: str
    content: str


@router.post("/query", response_model=SQLResponse)
async def query_database(
    request: SQLQuery,
    token_payload: dict = Depends(verify_token),
):
    """Agent SQL conversationnel — repond aux questions en francais."""
    user_id = int(token_payload.get("user_id", 0))
    company_id = int(token_payload.get("company_id", 0))

    result = await sql_agent_service.query(
        question=request.question,
        user_id=user_id,
        company_id=company_id,
    )
    return SQLResponse(
        answer=result["answer"],
        sql_query=result["sql_query"],
        data=result["data"],
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
