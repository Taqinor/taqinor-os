import os

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.endpoints import ocr, sql_agent
from app.core.database import create_tables
from app.core.security import verify_token

_DEBUG = os.environ.get("DJANGO_DEBUG", "True").lower() in ("true", "1", "yes")

app = FastAPI(
    title="ERP Agentique - FastAPI IA/OCR Service",
    description="Service FastAPI pour l'IA et l'OCR de l'ERP Agentique",
    version="1.0.0",
    root_path="/api/fastapi",
    docs_url="/docs" if _DEBUG else None,
    redoc_url="/redoc" if _DEBUG else None,
)

_ALLOWED_ORIGINS = os.environ.get(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    create_tables()


@app.get("/")
async def root():
    return {"message": "FastAPI IA/OCR Service is running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# With root_path="/api/fastapi", Starlette strips that prefix before routing.
# Routes must be registered at the path RELATIVE to root_path.
# nginx passes /api/fastapi/ocr/... → Starlette strips root_path → routes /ocr/...
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
