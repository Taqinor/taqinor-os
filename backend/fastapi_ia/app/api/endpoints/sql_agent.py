from fastapi import APIRouter
from pydantic import BaseModel

from app.services.sql_agent_service import sql_agent_service

router = APIRouter()


class SQLQuery(BaseModel):
    question: str


class SQLResponse(BaseModel):
    answer: str
    sql_query: str
    data: list | None = None


@router.post("/query", response_model=SQLResponse)
async def query_database(request: SQLQuery):
    """
    Agent SQL conversationnel (Phase 3 Sem. 5).
    En attendant, retourne une réponse placeholder.
    """
    result = await sql_agent_service.query(request.question)
    return SQLResponse(
        answer=result["answer"],
        sql_query=result["sql_query"],
        data=result["data"],
    )


@router.get("/schema")
async def get_schema():
    """Retourne un résumé du schéma de la base de données."""
    return await sql_agent_service.get_schema_summary()
