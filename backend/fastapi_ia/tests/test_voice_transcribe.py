"""AG10 — Transcription vocale assistant via Groq Whisper.

Couvre (avec l'appel Groq MOCKE — aucun reseau, aucune cle reelle en CI) :
  - Happy path : un clip retourne son transcript {text, language}.
  - Clip oversize (>25 Mo) rejete (413).
  - Type / magic bytes invalides rejetes (400).
  - Cle absente => degradation gracieuse (available=False, message clair),
    SANS appel reseau.
  - Rate limit fail-closed (503 si Redis injoignable) / 429 au-dela du plafond.
  - iOS Safari m4a/mp4 accepte (magic bytes ftyp a l'offset 4).

unittest (stdlib). A lancer depuis backend/fastapi_ia :
    python -m unittest discover -s tests
    (ou : python -m pytest tests -k voice)

Les modules importent fastapi ; si absent (env leger), les tests se sautent.
"""
import asyncio
import os
import sys
import unittest
from unittest import mock

os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from app.api.endpoints import voice as _ep
    from app.services import transcription_service as _svc_mod
    from app.services.transcription_service import (
        GroqTranscriptionService,
        TranscriptionUnavailableError,
    )
    from fastapi import HTTPException as _HTTPException
    _OK = True
    _ERR = None
except Exception as exc:  # pragma: no cover - fastapi absent
    _ep = None
    _svc_mod = None
    GroqTranscriptionService = None
    TranscriptionUnavailableError = Exception
    _HTTPException = None
    _OK = False
    _ERR = exc


def _run(coro):
    return asyncio.run(coro)


# Un blob webm valide (EBML magic) — passe la validation magic bytes.
_WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 64
# Un blob m4a/mp4 valide : "ftyp" a l'offset 4 (iOS Safari).
_M4A = b"\x00\x00\x00\x18ftypM4A " + b"\x00" * 32


class _FakeUpload:
    """Remplace UploadFile : .content_type, .filename, async .read(limit)."""

    def __init__(self, content_type, data, filename="clip"):
        self.content_type = content_type
        self.filename = filename
        self._data = data

    async def read(self, limit=-1):
        if limit is None or limit < 0:
            return self._data
        return self._data[:limit]


class _FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


class _FakeClient:
    """Remplace httpx.Client — aucune requete reseau reelle."""

    def __init__(self, response):
        self._response = response
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self._response


@unittest.skipUnless(_OK, f"endpoint voice indisponible: {_ERR}")
class GroqTranscriptionServiceTests(unittest.TestCase):
    def test_unavailable_without_key_raises(self):
        svc = GroqTranscriptionService()
        # `available` et `_transcribe_sync` lisent GROQ_API_KEY depuis config au
        # moment de l'appel (import paresseux) -> patcher la config suffit.
        with mock.patch("app.core.config.GROQ_API_KEY", ""):
            self.assertFalse(svc.available)
            with self.assertRaises(TranscriptionUnavailableError):
                _run(svc.transcribe(b"audio", filename="a.webm"))

    def test_happy_path_returns_text_and_language_mocked(self):
        svc = GroqTranscriptionService()
        fake_resp = _FakeResponse(
            200, {"text": "  bonjour le monde  ", "language": "fr"}
        )
        fake_client = _FakeClient(fake_resp)
        fake_httpx = mock.Mock()
        fake_httpx.Client = mock.Mock(return_value=fake_client)
        fake_httpx.Timeout = mock.Mock(return_value="timeout")
        with mock.patch("app.core.config.GROQ_API_KEY", "gsk_test"):
            with mock.patch.dict(sys.modules, {"httpx": fake_httpx}):
                result = _run(svc.transcribe(_WEBM, filename="clip.webm"))
        self.assertEqual(result["text"], "bonjour le monde")
        self.assertEqual(result["language"], "fr")
        # L'URL appelee est bien l'endpoint OpenAI-compatible de Groq.
        self.assertIn("audio/transcriptions", fake_client.calls[0][0])

    def test_groq_error_status_raises_runtime(self):
        svc = GroqTranscriptionService()
        fake_resp = _FakeResponse(500, {}, text="boom")
        fake_client = _FakeClient(fake_resp)
        fake_httpx = mock.Mock()
        fake_httpx.Client = mock.Mock(return_value=fake_client)
        fake_httpx.Timeout = mock.Mock(return_value="timeout")
        with mock.patch("app.core.config.GROQ_API_KEY", "gsk_test"):
            with mock.patch.dict(sys.modules, {"httpx": fake_httpx}):
                with self.assertRaises(RuntimeError):
                    _run(svc.transcribe(_WEBM, filename="clip.webm"))


@unittest.skipUnless(_OK, f"endpoint voice indisponible: {_ERR}")
class VoiceEndpointTests(unittest.TestCase):
    def test_missing_key_degrades_gracefully(self):
        # Cle absente -> available False -> reponse gracieuse, aucun appel reseau.
        with mock.patch.object(
            _svc_mod.groq_transcription_service.__class__, "available",
            new_callable=mock.PropertyMock, return_value=False,
        ):
            result = _run(
                _ep.transcribe(file=mock.Mock(), token_payload={"sub": "u"})
            )
        self.assertFalse(result.available)
        self.assertIn("groq_api_key", result.detail.lower())

    def test_happy_path_endpoint_returns_transcript(self):
        upload = _FakeUpload("audio/webm", _WEBM)
        with mock.patch.object(
            _svc_mod.groq_transcription_service.__class__, "available",
            new_callable=mock.PropertyMock, return_value=True,
        ):
            with mock.patch.object(_ep, "_check_rate_limit", return_value=None):
                with mock.patch.object(
                    _svc_mod.groq_transcription_service, "transcribe",
                    new=mock.AsyncMock(
                        return_value={"text": "salam", "language": "ar"}
                    ),
                ):
                    result = _run(
                        _ep.transcribe(file=upload, token_payload={"sub": "u"})
                    )
        self.assertTrue(result.available)
        self.assertEqual(result.text, "salam")
        self.assertEqual(result.language, "ar")

    def test_oversize_rejected_413(self):
        big = _WEBM + b"\x00" * (_ep.MAX_FILE_SIZE + 1)
        upload = _FakeUpload("audio/webm", big)
        with mock.patch.object(
            _svc_mod.groq_transcription_service.__class__, "available",
            new_callable=mock.PropertyMock, return_value=True,
        ):
            with mock.patch.object(_ep, "_check_rate_limit", return_value=None):
                with self.assertRaises(_HTTPException) as cm:
                    _run(_ep.transcribe(file=upload, token_payload={"sub": "u"}))
        self.assertEqual(cm.exception.status_code, 413)

    def test_invalid_content_type_rejected_400(self):
        upload = _FakeUpload("application/zip", _WEBM)
        with mock.patch.object(
            _svc_mod.groq_transcription_service.__class__, "available",
            new_callable=mock.PropertyMock, return_value=True,
        ):
            with mock.patch.object(_ep, "_check_rate_limit", return_value=None):
                with self.assertRaises(_HTTPException) as cm:
                    _run(_ep.transcribe(file=upload, token_payload={"sub": "u"}))
        self.assertEqual(cm.exception.status_code, 400)

    def test_invalid_magic_bytes_rejected_400(self):
        upload = _FakeUpload("audio/webm", b"NOT-A-WEBM-FILE-AT-ALL")
        with mock.patch.object(
            _svc_mod.groq_transcription_service.__class__, "available",
            new_callable=mock.PropertyMock, return_value=True,
        ):
            with mock.patch.object(_ep, "_check_rate_limit", return_value=None):
                with self.assertRaises(_HTTPException) as cm:
                    _run(_ep.transcribe(file=upload, token_payload={"sub": "u"}))
        self.assertEqual(cm.exception.status_code, 400)

    def test_ios_safari_m4a_accepted(self):
        upload = _FakeUpload("audio/mp4", _M4A)
        with mock.patch.object(
            _svc_mod.groq_transcription_service.__class__, "available",
            new_callable=mock.PropertyMock, return_value=True,
        ):
            with mock.patch.object(_ep, "_check_rate_limit", return_value=None):
                with mock.patch.object(
                    _svc_mod.groq_transcription_service, "transcribe",
                    new=mock.AsyncMock(
                        return_value={"text": "ok", "language": "fr"}
                    ),
                ):
                    result = _run(
                        _ep.transcribe(file=upload, token_payload={"sub": "u"})
                    )
        self.assertEqual(result.text, "ok")

    def test_magic_bytes_helpers(self):
        self.assertTrue(_ep._check_magic_bytes("audio/webm", _WEBM))
        self.assertFalse(_ep._check_magic_bytes("audio/webm", b"NOPE"))
        self.assertTrue(_ep._check_magic_bytes("audio/mp4", _M4A))
        self.assertFalse(_ep._check_magic_bytes("audio/mp4", b"ftyp-at-start"))

    def test_rate_limit_fail_closed_503(self):
        with mock.patch.object(
            _ep, "_get_redis", side_effect=RuntimeError("redis down")
        ):
            with self.assertRaises(_HTTPException) as cm:
                _ep._check_rate_limit("user-1")
        self.assertEqual(cm.exception.status_code, 503)

    def test_rate_limit_over_limit_429(self):
        fake_redis = mock.Mock()
        pipe = mock.Mock()
        pipe.execute.return_value = [0, 1, _ep.RATE_LIMIT_MAX + 1, True]
        fake_redis.pipeline.return_value = pipe
        with mock.patch.object(_ep, "_get_redis", return_value=fake_redis):
            with self.assertRaises(_HTTPException) as cm:
                _ep._check_rate_limit("user-1")
        self.assertEqual(cm.exception.status_code, 429)


if __name__ == "__main__":
    unittest.main()
