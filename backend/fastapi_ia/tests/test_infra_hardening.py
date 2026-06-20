"""ERR85 / ERR86 — Durcissement infra du service FastAPI.

  - ERR85 : create_tables() ne lance du DDL (ALTER/CREATE INDEX) en owner QUE si
    RUN_DB_DDL est explicitement active ; par defaut c'est un no-op.
  - ERR86 : le rate-limit OCR echoue FERME (503) si Redis est indisponible, au
    lieu de laisser passer (sinon le plafond payant Zhipu serait desactive).

unittest (stdlib). A lancer depuis backend/fastapi_ia :
    python -m unittest discover -s tests

Ces modules importent sqlalchemy / fastapi ; si ces deps manquent (env leger),
les tests se sautent proprement.
"""
import os
import sys
import unittest
from unittest import mock

os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── ERR85 — gating DDL ────────────────────────────────────────────────────────
try:
    from app.core import database as _db
    _DB_OK = True
    _DB_ERR = None
except Exception as exc:  # pragma: no cover - sqlalchemy absent
    _db = None
    _DB_OK = False
    _DB_ERR = exc


@unittest.skipUnless(_DB_OK, f"app.core.database indisponible: {_DB_ERR}")
class DdlGatingTests(unittest.TestCase):
    def test_ddl_disabled_by_default(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("RUN_DB_DDL", None)
            self.assertFalse(_db._ddl_enabled())

    def test_ddl_enabled_with_flag(self):
        for val in ("1", "true", "yes", "TRUE"):
            with mock.patch.dict(os.environ, {"RUN_DB_DDL": val}):
                self.assertTrue(_db._ddl_enabled(), val)

    def test_create_tables_noop_when_disabled(self):
        # Sans le flag, create_tables() ne doit toucher NI le metadata NI le DDL.
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("RUN_DB_DDL", None)
            with mock.patch.object(_db.Base.metadata, "create_all") as m_create, \
                    mock.patch.object(_db.engine, "begin") as m_begin:
                _db.create_tables()
                m_create.assert_not_called()
                m_begin.assert_not_called()


# ── ERR86 — rate-limit OCR fail-closed ────────────────────────────────────────
try:
    from app.api.endpoints import ocr as _ocr
    from fastapi import HTTPException as _HTTPException
    _OCR_OK = True
    _OCR_ERR = None
except Exception as exc:  # pragma: no cover - fastapi absent
    _ocr = None
    _HTTPException = None
    _OCR_OK = False
    _OCR_ERR = exc


@unittest.skipUnless(_OCR_OK, f"app.api.endpoints.ocr indisponible: {_OCR_ERR}")
class RateLimitFailClosedTests(unittest.TestCase):
    def test_redis_error_denies_with_503(self):
        # _get_redis() leve -> on doit refuser (503), pas laisser passer.
        with mock.patch.object(
            _ocr, "_get_redis", side_effect=RuntimeError("redis down")
        ):
            with self.assertRaises(_HTTPException) as cm:
                _ocr._check_rate_limit("user-1")
            self.assertEqual(cm.exception.status_code, 503)

    def test_over_limit_raises_429(self):
        # Redis OK mais compteur > plafond -> 429.
        fake_redis = mock.Mock()
        pipe = mock.Mock()
        pipe.execute.return_value = [0, 1, _ocr.RATE_LIMIT_MAX + 1, True]
        fake_redis.pipeline.return_value = pipe
        with mock.patch.object(_ocr, "_get_redis", return_value=fake_redis):
            with self.assertRaises(_HTTPException) as cm:
                _ocr._check_rate_limit("user-1")
            self.assertEqual(cm.exception.status_code, 429)

    def test_under_limit_passes(self):
        fake_redis = mock.Mock()
        pipe = mock.Mock()
        pipe.execute.return_value = [0, 1, 1, True]
        fake_redis.pipeline.return_value = pipe
        with mock.patch.object(_ocr, "_get_redis", return_value=fake_redis):
            # Ne doit pas lever.
            _ocr._check_rate_limit("user-1")


if __name__ == "__main__":
    unittest.main()
