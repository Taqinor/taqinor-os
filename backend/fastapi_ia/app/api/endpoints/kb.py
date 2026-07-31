"""WIR60 — Assistant IA d'écriture & résumé de l'éditeur KB (XKB23).

`AiWritingToolbar.jsx` (frontend/src/features/kb) appelle
`iaApi.kbRedaction()` -> `POST /kb/redaction`, mais aucun routeur `/kb`
n'existait dans ce service : générer/reformuler/corriger/traduire/résumer
échouaient tous en 404 (toast propre côté UI, fonctionnalité 100 % inopérante).

Cet endpoint REUTILISE le même LLM key-gated que l'agent SQL
(`app.services.sql_agent_service.SQLAgentService._build_llm`, providers
groq/openai/claude/ollama pilotés par `SQL_AGENT_PROVIDER`/`SQL_AGENT_MODEL`)
— AUCUNE nouvelle dépendance, AUCUN nouveau service payant. Sans clé
configurée, `_build_llm()` lève `RuntimeError("<PROVIDER>_API_KEY manquante
dans .env")` : on la traduit en 503 avec ce même message, que le frontend
reconnaît déjà (`isKeyMissing` dans `features/kb/aiWriting.js`) pour afficher
« Assistant indisponible (configuration manquante). » — dégradation gracieuse,
jamais un crash silencieux.
"""
import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.security import verify_token

logger = logging.getLogger(__name__)

router = APIRouter()

# Instructions système par action — cf. `AI_ACTIONS` dans
# `frontend/src/features/kb/aiWriting.js` (même liste, même ordre).
_SYSTEM_PROMPTS: dict[str, str] = {
    "generer": (
        "Tu es un rédacteur technique francophone pour une base de "
        "connaissances (KB) interne d'entreprise. Rédige un article clair, "
        "structuré (titre implicite + paragraphes courts) à partir du texte "
        "de départ fourni par l'utilisateur. N'invente aucun fait précis "
        "(chiffre, nom, date) qui ne serait pas dans le texte de départ — "
        "reste générique si l'information manque. Réponds UNIQUEMENT avec "
        "le texte rédigé, sans préambule ni commentaire."
    ),
    "reformuler": (
        "Reformule le texte suivant en français : garde le sens exact, "
        "améliore la clarté et le style. Réponds UNIQUEMENT avec le texte "
        "reformulé, sans préambule ni commentaire."
    ),
    "corriger": (
        "Corrige l'orthographe, la grammaire et la ponctuation du texte "
        "suivant en français, sans changer le sens ni le style. Réponds "
        "UNIQUEMENT avec le texte corrigé, sans préambule ni commentaire."
    ),
    "traduire_fr_ar": (
        "Traduis le texte suivant du français vers l'arabe standard. "
        "Réponds UNIQUEMENT avec la traduction, sans préambule ni "
        "commentaire."
    ),
    "traduire_ar_fr": (
        "Traduis le texte suivant de l'arabe vers le français. Réponds "
        "UNIQUEMENT avec la traduction, sans préambule ni commentaire."
    ),
    "resumer": (
        "Résume le texte suivant en français en un court paragraphe "
        "(chapeau d'introduction, 2-3 phrases maximum). Réponds UNIQUEMENT "
        "avec le résumé, sans préambule ni commentaire."
    ),
}

_MAX_CHARS = 20_000  # borne large mais finie — jamais un prompt sans limite.


class RedactionRequest(BaseModel):
    action: str
    texte: str = ""
    contexte: str = ""


class RedactionResponse(BaseModel):
    texte: str


def _build_human_message(texte: str, contexte: str) -> str:
    texte = (texte or "").strip()
    contexte = (contexte or "").strip()
    if contexte and texte:
        return f"Contexte : {contexte}\n\nTexte :\n{texte}"
    return texte or contexte


def _run_redaction(action: str, texte: str, contexte: str) -> str:
    """Appel LLM synchrone (exécuté dans un thread par l'endpoint).

    Réutilise `SQLAgentService._build_llm()` — même factory/provider/clé que
    l'agent SQL. Lève `RuntimeError` si la clé du provider configuré est
    absente (traduit en 503 par l'endpoint) ; toute autre exception remonte
    telle quelle (traduite en 502 par l'endpoint)."""
    from app.services.sql_agent_service import SQLAgentService
    from langchain_core.messages import HumanMessage, SystemMessage

    llm = SQLAgentService._build_llm()
    human = _build_human_message(texte, contexte)[:_MAX_CHARS]
    response = llm.invoke([
        SystemMessage(content=_SYSTEM_PROMPTS[action]),
        HumanMessage(content=human),
    ])
    content = getattr(response, "content", "") or ""
    return content.strip() if isinstance(content, str) else str(content).strip()


@router.post("/redaction", response_model=RedactionResponse)
async def redaction(
    request: RedactionRequest,
    token_payload: dict = Depends(verify_token),
):
    """Génère/reformule/corrige/traduit/résume le texte de l'éditeur KB.

    `action` doit être une des clés de `_SYSTEM_PROMPTS` (même liste que
    `AI_ACTIONS` côté frontend). `texte` et/ou `contexte` doivent contenir au
    moins quelque chose — sinon 400 (jamais un appel LLM sur un prompt vide).
    """
    action = (request.action or "").strip()
    if action not in _SYSTEM_PROMPTS:
        raise HTTPException(
            status_code=400,
            detail=f"Action inconnue : '{action}'.",
        )

    texte = (request.texte or "").strip()
    contexte = (request.contexte or "").strip()
    if not texte and not contexte:
        raise HTTPException(
            status_code=400,
            detail="Texte ou contexte requis pour l'assistant d'écriture.",
        )

    try:
        result = await asyncio.to_thread(_run_redaction, action, texte, contexte)
    except RuntimeError as exc:
        # Clé LLM absente (même message que l'agent SQL) — dégradation
        # gracieuse reconnue par `isKeyMissing` côté frontend.
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:  # noqa: BLE001 — jamais un 500 nu vers l'UI.
        logger.error("KB redaction error (action=%s): %s", action, exc)
        raise HTTPException(
            status_code=502,
            detail="L'assistant n'a pas pu traiter la demande. Réessayez.",
        )

    if not result:
        raise HTTPException(
            status_code=502,
            detail="L'assistant n'a renvoyé aucun résultat. Réessayez.",
        )

    return RedactionResponse(texte=result)
