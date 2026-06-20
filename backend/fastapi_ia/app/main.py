import os

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.endpoints import ocr, sql_agent
from app.core.database import create_tables
from app.core.security import verify_token

# ERR42 — fail-closed : _DEBUG defaut False. /docs et /redoc (divulgation de
# schema) restent fermes en production sauf si DJANGO_DEBUG est EXPLICITEMENT
# active. Le dev local active toujours le mode debug via .env (DJANGO_DEBUG=1).
_DEBUG = os.environ.get("DJANGO_DEBUG", "False").lower() in ("true", "1", "yes")

app = FastAPI(
    title="ERP Agentique - FastAPI IA/OCR Service",
    description="Service FastAPI pour l'IA et l'OCR de l'ERP Agentique",
    version="1.0.0",
    root_path="/api/fastapi",
    # Schemas interactifs gates sur le debug (fermes par defaut).
    docs_url="/docs" if _DEBUG else None,
    redoc_url="/redoc" if _DEBUG else None,
    openapi_url="/openapi.json" if _DEBUG else None,
)

_ALLOWED_ORIGINS = os.environ.get(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-CSRFToken", "Accept"],
)


@app.on_event("startup")
def on_startup():
    create_tables()
    # Pre-charge le modele sentence-transformers en arriere-plan
    # pour que le premier appel SQL agent soit rapide
    import threading
    from app.services.sql_agent_service import sql_agent_service
    t = threading.Thread(target=sql_agent_service._get_embeddings, daemon=True)
    t.start()


@app.get("/health")
async def health_check():
    return {"status": "ok"}


# root_path="/api/fastapi" — Starlette strips the prefix before routing.
# Register routes relative to root_path (e.g. /ocr, not /api/fastapi/ocr).
app.include_router(
    ocr.router,
    prefix="/ocr",
    tags=["OCR"],
    dependencies=[Depends(verify_token)],
)
app.include_router(
    sql_agent.router,
    prefix="/sql-agent",
    tags=["SQL Agent"],
    dependencies=[Depends(verify_token)],
)
