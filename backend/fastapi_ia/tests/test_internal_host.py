"""AANA52 — les appels internes FastAPI -> Django portent un Host autorise.

Sans cela Django repond 400 DisallowedHost sur `django_core:8000` : la lecture
des permissions (/auth/me/) echoue fermee et tous les outils d'action tombent.
httpx.Client est remplace par un client enregistreur ; le helper n'est pas moque.
"""
import os
import sys
import unittest
from unittest import mock

os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import action_tools as at  # noqa: E402
from app.services.action_tools import ActionContext  # noqa: E402

_ENV_KEYS = ("DJANGO_ALLOWED_HOSTS", "DJANGO_INTERNAL_HOST")


class _Resp:
    status_code = 200

    def __init__(self, payload):
        self._p = payload

    def json(self):
        return self._p


class _RecordingClient:
    calls: list = []

    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def request(self, verb, url, **kwargs):
        _RecordingClient.calls.append((verb, url, kwargs.get("headers", {})))
        return _Resp({"permissions": ["prix_achat_voir"], "actions": []})


def _ctx():
    return ActionContext(company_id=1, role="responsable", permissions=[],
                         token="jwt-xyz")


class InternalHostTests(unittest.TestCase):
    def setUp(self):
        _RecordingClient.calls = []

    def _env(self, **env):
        base = {k: v for k, v in os.environ.items() if k not in _ENV_KEYS}
        base.update(env)
        return mock.patch.dict(os.environ, base, clear=True)

    def _run(self, fn):
        with mock.patch.object(at.httpx, "Client", _RecordingClient), \
                mock.patch.object(at, "DJANGO_INTERNAL_URL",
                                  "http://django_core:8000"):
            out = fn()
        self.assertEqual(len(_RecordingClient.calls), 1)
        return out, _RecordingClient.calls[0][2]

    def test_action_path_host_from_allowed_hosts(self):
        with self._env(DJANGO_ALLOWED_HOSTS="api.taqinor.ma,other"):
            _, headers = self._run(
                lambda: at._django_call(_ctx(), "/x/", method="GET"))
        self.assertEqual(headers.get("Host"), "api.taqinor.ma")

    def test_permissions_path_host_from_allowed_hosts(self):
        with self._env(DJANGO_ALLOWED_HOSTS="api.taqinor.ma,other"):
            perms, headers = self._run(
                lambda: at.fetch_caller_permissions(_ctx()))
        self.assertEqual(headers.get("Host"), "api.taqinor.ma")
        self.assertEqual(perms, ["prix_achat_voir"])

    def test_catalogue_path_host(self):
        with self._env(DJANGO_ALLOWED_HOSTS="api.taqinor.ma"):
            _, headers = self._run(lambda: at.fetch_catalogue(_ctx()))
        self.assertEqual(headers.get("Host"), "api.taqinor.ma")

    def test_explicit_internal_host_wins(self):
        with self._env(DJANGO_ALLOWED_HOSTS="api.taqinor.ma",
                       DJANGO_INTERNAL_HOST="interne.taqinor.ma"):
            _, h1 = self._run(lambda: at._django_call(_ctx(), "/x/", "GET"))
            _RecordingClient.calls = []
            _, h2 = self._run(lambda: at.fetch_caller_permissions(_ctx()))
        self.assertEqual(h1.get("Host"), "interne.taqinor.ma")
        self.assertEqual(h2.get("Host"), "interne.taqinor.ma")

    def test_wildcard_means_no_override(self):
        for hosts in ("*", ".taqinor.ma,*", ""):
            _RecordingClient.calls = []
            with self._env(DJANGO_ALLOWED_HOSTS=hosts):
                _, h1 = self._run(
                    lambda: at._django_call(_ctx(), "/x/", "GET"))
                _RecordingClient.calls = []
                _, h2 = self._run(
                    lambda: at.fetch_caller_permissions(_ctx()))
            self.assertNotIn("Host", h1, hosts)
            self.assertNotIn("Host", h2, hosts)

    def test_leading_dot_entry_skipped_for_next(self):
        with self._env(DJANGO_ALLOWED_HOSTS=".taqinor.ma, api.taqinor.ma"):
            _, headers = self._run(
                lambda: at._django_call(_ctx(), "/x/", "GET"))
        self.assertEqual(headers.get("Host"), "api.taqinor.ma")


if __name__ == "__main__":
    unittest.main()
