"""S10 — Endpoint de transcription audio (chat vocal) — Whisper auto-heberge.

POST /transcribe : transcrit un blob audio uploade en `{text, language}` via
faster-whisper (FR / AR / Darija, auto-detection avec indice facultatif).

Derriere le flag CHAT_TRANSCRIPTION_ENABLED :
  - OFF (defaut) => reponse gracieuse {"enabled": false, ...} (PAS une erreur) ;
    le modele n'est jamais charge ni telecharge.
  - ON => transcription reelle (modele charge paresseusement au premier appel).

Protections calquees sur l'OCR : JWT (via le routeur), validation Content-Type,
limite de taille, magic bytes audio, rate limit fail-closed.
"""
import os
import time

import redis
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.core.security import verify_token
from app.services.transcription_service import (
    TranscriptionDisabledError,
    transcription_service,
)

router = APIRouter()

# ── Constantes de securite ────────────────────────────────────────────────────
MAX_FILE_SIZE = 25 * 1024 * 1024   # 25 Mo — messages vocaux courts
RATE_LIMIT_MAX = 60                 # requetes max
RATE_LIMIT_WINDOW = 3600            # par heure (en secondes)

# Formats audio courants acceptes (webm/ogg/m4a/mp4/wav).
ACCEPTED_CONTENT_TYPES = (
    "audio/webm",
    "audio/ogg",
    "audio/mp4",
    "audio/m4a",
    "audio/x-m4a",
    "audio/mpeg",
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "video/mp4",   # certains navigateurs etiquettent un .mp4 audio ainsi
    "video/webm",
)

# Extension de fichier temporaire selon le type — aide ffmpeg/faster-whisper.
_SUFFIX_BY_TYPE = {
    "audio/webm": ".webm",
    "video/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/mp4": ".mp4",
    "audio/m4a": ".m4a",
    "audio/x-m4a": ".m4a",
    "video/mp4": ".mp4",
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/wave": ".wav",
}

# Signatures (magic bytes) pour confirmer que le contenu correspond au type.
MAGIC_BYTES: dict[str, list[bytes]] = {
    "audio/webm": [b"\x1a\x45\xdf\xa3"],
    "video/webm": [b"\x1a\x45\xdf\xa3"],
    "audio/ogg": [b"OggS"],
    "audio/wav": [b"RIFF"],
    "audio/x-wav": [b"RIFF"],
    "audio/wave": [b"RIFF"],
    "audio/mpeg": [b"ID3", b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"],
    # m4a / mp4 : la boite "ftyp" est aux octets 4..8.
    "audio/mp4": [b"ftyp"],
    "audio/m4a": [b"ftyp"],
    "audio/x-m4a": [b"ftyp"],
    "video/mp4": [b"ftyp"],
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
    if not signatures:
        return True
    for sig in signatures:
        # mp4/m4a : "ftyp" attendu juste apres la taille de la 1ere boite.
        if sig == b"ftyp":
            if data[4:8] == b"ftyp":
                return True
            continue
        if data[: len(sig)] == sig:
            return True
    return False


def _check_rate_limit(user_id: str) -> None:
    """Plafonne la transcription par utilisateur — FAIL CLOSED (comme l'OCR).

    Si Redis est injoignable on REFUSE (503) au lieu de laisser passer : une
    panne ne doit pas desactiver silencieusement le plafond.
    """
    try:
        r = _get_redis()
        key = f"transcribe_rate:{user_id}"
        now = time.time()
        window_start = now - RATE_LIMIT_WINDOW

        pipe = r.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zadd(key, {str(now): now})
        pipe.zcard(key)
        pipe.expire(key, RATE_LIMIT_WINDOW)
        results = pipe.execute()
        count = results[2]
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=503,
            detail=(
                "Service de limitation temporairement indisponible. "
                "Réessayez dans quelques instants."
            ),
        )

    if count > RATE_LIMIT_MAX:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Limite atteinte : {RATE_LIMIT_MAX} transcriptions par heure. "
                "Réessayez plus tard."
            ),
        )


# ── Schemas ────────────────────────────────────────────────────────────────────

class TranscriptionResult(BaseModel):
    text: str = ""
    language: str = ""
    enabled: bool = True
    # Message informatif quand la transcription est desactivee.
    detail: str = ""


# ── Endpoint ────────────────────────────────────────────────────────────────────

@router.post("/transcribe", response_model=TranscriptionResult)
async def transcribe(
    file: UploadFile = File(...),
    token_payload: dict = Depends(verify_token),
):
    """Transcrit un message vocal en texte (FR / AR / Darija).

    Flag OFF => reponse gracieuse {"enabled": false} (200), aucun modele charge.
    Flag ON  => {"text", "language", "enabled": true}.
    """
    if not transcription_service.enabled:
        # Degradation gracieuse — PAS une erreur (le front masque le micro).
        return TranscriptionResult(
            enabled=False,
            detail="La transcription vocale est désactivée.",
        )

    user_id = str(
        token_payload.get("user_id", token_payload.get("sub", "anonymous"))
    )
    _check_rate_limit(user_id)

    if not file.content_type or file.content_type not in ACCEPTED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Type audio non accepté : '{file.content_type}'. "
                f"Formats acceptés : {', '.join(ACCEPTED_CONTENT_TYPES)}"
            ),
        )

    contents = await file.read(MAX_FILE_SIZE + 1)
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="Fichier audio trop volumineux (max 25 Mo).",
        )
    if not contents:
        raise HTTPException(status_code=400, detail="Fichier audio vide.")

    if not _check_magic_bytes(file.content_type, contents):
        raise HTTPException(
            status_code=400,
            detail="Le contenu du fichier ne correspond pas au type audio déclaré.",
        )

    suffix = _SUFFIX_BY_TYPE.get(file.content_type, "")
    try:
        result = await transcription_service.transcribe(contents, suffix=suffix)
    except TranscriptionDisabledError:
        # Course rare : le flag a ete coupe entre le check et l'appel.
        return TranscriptionResult(
            enabled=False,
            detail="La transcription vocale est désactivée.",
        )

    return TranscriptionResult(
        text=result.get("text", ""),
        language=result.get("language", ""),
        enabled=True,
    )
