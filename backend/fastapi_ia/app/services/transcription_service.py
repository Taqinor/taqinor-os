"""Service de transcription audio — Whisper auto-heberge (faster-whisper).

S10 — transcription du chat vocal (FR / AR / Darija marocaine).

Principes (CLAUDE.md / spec S10) :
  - Derriere le flag CHAT_TRANSCRIPTION_ENABLED : quand il est OFF, l'endpoint
    repond "disabled" de maniere gracieuse (jamais une erreur) et CE SERVICE
    n'importe meme pas faster-whisper.
  - Chargement PARESSEUX du modele + cache de telechargement : le modele est
    telecharge au PREMIER appel uniquement (jamais a l'import, ni au build de
    l'image, ni au demarrage du service). L'import de `faster_whisper` reste
    local a la methode pour que importer ce module — ou demarrer le service —
    n'exige ni le paquet ni les poids ni le reseau (CI verte sans telechargement).
  - Auto-detection de la langue avec un indice FR/AR/Darija facultatif
    (WHISPER_LANGUAGE_HINT ; "ar" couvre la Darija).
"""
from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import threading
from typing import Any

from app.core.config import (
    CHAT_TRANSCRIPTION_ENABLED,
    WHISPER_CACHE_DIR,
    WHISPER_LANGUAGE_HINT,
    WHISPER_MODEL_SIZE,
)

logger = logging.getLogger(__name__)


class TranscriptionDisabledError(RuntimeError):
    """Leve quand la transcription est demandee alors que le flag est OFF."""


class TranscriptionUnavailableError(RuntimeError):
    """Leve quand la cle Groq est absente (degradation gracieuse cote endpoint).

    AG10 — l'endpoint /sql-agent/transcribe la traduit en reponse claire
    {"available": false, "detail": ...} plutot qu'en 500.
    """


class TranscriptionService:
    """Wrapper paresseux autour de faster-whisper.

    Le modele est instancie une seule fois (au premier appel) et reutilise.
    Tout l'acces au modele est lazy : ni l'import du paquet, ni le
    telechargement des poids n'ont lieu avant le premier appel reel.
    """

    def __init__(self) -> None:
        self._model: Any = None
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return CHAT_TRANSCRIPTION_ENABLED

    def _load_model(self) -> Any:
        """Charge (et met en cache) le modele faster-whisper — lazy + thread-safe.

        Import LOCAL : sans cet appel, `faster_whisper` n'est jamais importe, donc
        le module et le service demarrent meme si le paquet est absent ou si le
        flag est OFF.
        """
        if self._model is not None:
            return self._model
        with self._lock:
            if self._model is not None:
                return self._model
            # Import paresseux — surtout pas au niveau module.
            from faster_whisper import WhisperModel

            kwargs: dict[str, Any] = {
                # CPU + int8 : leger et suffisant pour des messages vocaux courts.
                "device": "cpu",
                "compute_type": "int8",
            }
            if WHISPER_CACHE_DIR:
                kwargs["download_root"] = WHISPER_CACHE_DIR
            logger.info(
                "Chargement du modele faster-whisper '%s' (premier appel)",
                WHISPER_MODEL_SIZE,
            )
            self._model = WhisperModel(WHISPER_MODEL_SIZE, **kwargs)
            return self._model

    def _transcribe_sync(self, audio_bytes: bytes, suffix: str) -> dict[str, Any]:
        """Transcription bloquante — appelee dans un thread executor."""
        if not self.enabled:
            raise TranscriptionDisabledError("transcription disabled")

        model = self._load_model()

        # faster-whisper lit un chemin de fichier ; on ecrit le blob dans un
        # fichier temporaire supprime ensuite.
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                suffix=suffix or ".bin", delete=False
            ) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name

            language = WHISPER_LANGUAGE_HINT or None  # None => auto-detection
            segments, info = model.transcribe(
                tmp_path,
                language=language,
                task="transcribe",
                vad_filter=True,
            )
            text = "".join(segment.text for segment in segments).strip()
            detected = getattr(info, "language", None) or language or ""
            return {"text": text, "language": detected}
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:  # pragma: no cover - best effort cleanup
                    pass

    async def transcribe(
        self, audio_bytes: bytes, *, suffix: str = ""
    ) -> dict[str, Any]:
        """Transcrit un blob audio en `{text, language}`.

        Leve TranscriptionDisabledError si le flag est OFF (l'endpoint la
        traduit en reponse gracieuse "disabled").
        """
        if not self.enabled:
            raise TranscriptionDisabledError("transcription disabled")
        return await asyncio.to_thread(self._transcribe_sync, audio_bytes, suffix)


# Instance partagee (modele charge paresseusement au premier usage).
transcription_service = TranscriptionService()


# ── AG10 — Transcription vocale de l'assistant via Groq Whisper ────────────────
#
# Chemin DISTINCT du self-heberge S10 ci-dessus : il sert le micro de
# l'assistant et appelle l'API OpenAI-compatible de Groq (whisper-large-v3) en
# REUTILISANT GROQ_API_KEY — aucun nouveau service payant, aucun poids local.
#
#   - Cle absente => degradation gracieuse : `available` est False et
#     `transcribe` leve TranscriptionUnavailableError (message clair cote
#     endpoint), JAMAIS un 500 opaque.
#   - Imports PARESSEUX (httpx + config Groq locaux a la methode) pour que ce
#     module s'importe sans la cle ni httpx presents.
#   - Aucun transcript persiste : on renvoie juste {text, language}.


class GroqTranscriptionService:
    """Transcription vocale assistant via l'API Groq (OpenAI-compatible).

    Sans etat (pas de modele a charger) : chaque appel poste l'audio a l'endpoint
    `audio/transcriptions` de Groq avec la cle existante.
    """

    @property
    def available(self) -> bool:
        """Vrai uniquement si GROQ_API_KEY est configuree."""
        from app.core.config import GROQ_API_KEY

        return bool(GROQ_API_KEY)

    def _transcribe_sync(self, audio_bytes: bytes, filename: str) -> dict[str, Any]:
        # Imports PARESSEUX : le module s'importe meme sans httpx ni cle.
        import httpx

        from app.core.config import (
            GROQ_API_BASE_URL,
            GROQ_API_KEY,
            GROQ_WHISPER_LANGUAGE_HINT,
            GROQ_WHISPER_MODEL,
        )

        if not GROQ_API_KEY:
            raise TranscriptionUnavailableError("GROQ_API_KEY manquante")

        url = f"{GROQ_API_BASE_URL.rstrip('/')}/audio/transcriptions"
        data: dict[str, str] = {
            "model": GROQ_WHISPER_MODEL,
            "response_format": "json",
        }
        language = GROQ_WHISPER_LANGUAGE_HINT or None  # None => auto-detection
        if language:
            data["language"] = language

        files = {
            "file": (filename or "audio", audio_bytes, "application/octet-stream"),
        }
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}

        timeout = httpx.Timeout(60.0, connect=5.0)
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, headers=headers, data=data, files=files)

        if resp.status_code != 200:
            logger.warning(
                "Groq transcription a echoue (%s) : %s",
                resp.status_code,
                resp.text[:300],
            )
            raise RuntimeError(
                f"Le service de transcription a renvoye une erreur ({resp.status_code})."
            )

        payload = resp.json()
        text = (payload.get("text") or "").strip()
        detected = payload.get("language") or language or ""
        return {"text": text, "language": detected}

    async def transcribe(
        self, audio_bytes: bytes, *, filename: str = ""
    ) -> dict[str, Any]:
        """Transcrit un blob audio via Groq en `{text, language}`.

        Leve TranscriptionUnavailableError si la cle est absente (l'endpoint la
        traduit en reponse gracieuse "indisponible").
        """
        if not self.available:
            raise TranscriptionUnavailableError("GROQ_API_KEY manquante")
        return await asyncio.to_thread(self._transcribe_sync, audio_bytes, filename)


# Instance partagee — sans etat, sur (n'importe ni httpx ni la cle a l'import).
groq_transcription_service = GroqTranscriptionService()
