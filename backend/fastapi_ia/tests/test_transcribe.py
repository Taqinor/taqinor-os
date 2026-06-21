"""S10 — Endpoint de transcription audio (Whisper auto-heberge, faster-whisper).

Couvre :
  - Flag OFF => l'endpoint repond "disabled" gracieusement (enabled=False),
    SANS charger ni telecharger le moindre poids (le service n'appelle jamais
    faster-whisper).
  - Flag ON  => une transcription reelle est retournee {text, language}, avec le
    MODELE MOCKE : aucun poids reel, aucun reseau dans la CI.
  - Le chargement du modele est PARESSEUX (l'import de faster_whisper est local).

unittest (stdlib). A lancer depuis backend/fastapi_ia :
    python -m unittest discover -s tests
    (ou : python -m pytest tests -k transcribe)

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
    from app.api.endpoints import transcription as _ep
    from app.services import transcription_service as _svc_mod
    from app.services.transcription_service import (
        TranscriptionDisabledError,
        TranscriptionService,
    )
    from fastapi import HTTPException as _HTTPException
    _OK = True
    _ERR = None
except Exception as exc:  # pragma: no cover - fastapi absent
    _ep = None
    _svc_mod = None
    TranscriptionService = None
    TranscriptionDisabledError = Exception
    _HTTPException = None
    _OK = False
    _ERR = exc


def _run(coro):
    return asyncio.run(coro)


class _FakeSegment:
    def __init__(self, text):
        self.text = text


class _FakeInfo:
    def __init__(self, language):
        self.language = language


class _FakeWhisperModel:
    """Remplace faster_whisper.WhisperModel — aucun poids, aucun reseau."""

    instances = 0

    def __init__(self, *args, **kwargs):
        type(self).instances += 1
        self.args = args
        self.kwargs = kwargs

    def transcribe(self, path, **kwargs):
        return ([_FakeSegment("bonjour "), _FakeSegment("le monde")], _FakeInfo("fr"))


@unittest.skipUnless(_OK, f"endpoint transcription indisponible: {_ERR}")
class TranscriptionServiceTests(unittest.TestCase):
    def test_disabled_raises_disabled_error(self):
        svc = TranscriptionService()
        with mock.patch.object(
            TranscriptionService, "enabled",
            new_callable=mock.PropertyMock, return_value=False,
        ):
            with self.assertRaises(TranscriptionDisabledError):
                _run(svc.transcribe(b"fake-audio", suffix=".wav"))

    def test_enabled_returns_text_and_language_with_mocked_model(self):
        _FakeWhisperModel.instances = 0
        svc = TranscriptionService()
        fake_module = mock.Mock()
        fake_module.WhisperModel = _FakeWhisperModel
        with mock.patch.object(
            TranscriptionService, "enabled",
            new_callable=mock.PropertyMock, return_value=True,
        ):
            # Le service importe faster_whisper LOCALEMENT -> on injecte un faux
            # module : aucun vrai poids n'est jamais telecharge.
            with mock.patch.dict(sys.modules, {"faster_whisper": fake_module}):
                result = _run(svc.transcribe(b"fake-audio", suffix=".wav"))
        self.assertEqual(result["text"], "bonjour le monde")
        self.assertEqual(result["language"], "fr")
        # Modele instancie une seule fois (cache paresseux).
        self.assertEqual(_FakeWhisperModel.instances, 1)

    def test_model_loaded_once_and_lazily(self):
        _FakeWhisperModel.instances = 0
        svc = TranscriptionService()
        # Avant tout appel : modele non charge (lazy).
        self.assertIsNone(svc._model)
        fake_module = mock.Mock()
        fake_module.WhisperModel = _FakeWhisperModel
        with mock.patch.object(
            TranscriptionService, "enabled",
            new_callable=mock.PropertyMock, return_value=True,
        ):
            with mock.patch.dict(sys.modules, {"faster_whisper": fake_module}):
                _run(svc.transcribe(b"a", suffix=".wav"))
                _run(svc.transcribe(b"b", suffix=".wav"))
        self.assertEqual(_FakeWhisperModel.instances, 1)


@unittest.skipUnless(_OK, f"endpoint transcription indisponible: {_ERR}")
class TranscriptionEndpointTests(unittest.TestCase):
    def test_endpoint_disabled_reports_disabled_not_error(self):
        # Flag OFF -> reponse gracieuse, aucun rate-limit ni modele declenches.
        with mock.patch.object(
            _svc_mod.transcription_service.__class__, "enabled",
            new_callable=mock.PropertyMock, return_value=False,
        ):
            result = _run(_ep.transcribe(file=mock.Mock(), token_payload={"sub": "u"}))
        self.assertFalse(result.enabled)
        self.assertIn("désactiv", result.detail.lower())

    def test_magic_bytes_webm(self):
        self.assertTrue(_ep._check_magic_bytes("audio/webm", b"\x1a\x45\xdf\xa3rest"))
        self.assertFalse(_ep._check_magic_bytes("audio/webm", b"NOTWEBM"))

    def test_magic_bytes_wav(self):
        self.assertTrue(_ep._check_magic_bytes("audio/wav", b"RIFF....WAVE"))

    def test_magic_bytes_mp4_ftyp_offset(self):
        # "ftyp" attendu aux octets 4..8.
        self.assertTrue(_ep._check_magic_bytes("audio/mp4", b"\x00\x00\x00\x18ftypM4A "))
        self.assertFalse(_ep._check_magic_bytes("audio/mp4", b"ftyp at start"))

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
