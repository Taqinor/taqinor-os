"""ADCG14 — santé des services vitaux dans docker-compose.yml (+ docker-compose.prod.yml).

Nouveau fichier car : aucun module de test pour les fichiers compose (texte de la tâche).
Lecture PyYAML (installé avant le runner) ; la balise compose `!reset` est acceptée.
Run:
    python -m unittest scripts.tests.test_docker_compose -v
"""
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent


class _Chargeur(yaml.SafeLoader):
    pass


_Chargeur.add_constructor("!reset", lambda loader, node: None)


def _services():
    """Services de docker-compose.yml, clés de docker-compose.prod.yml superposées."""
    base = yaml.load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"), Loader=_Chargeur)
    prod = yaml.load((ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8"), Loader=_Chargeur)
    services = base["services"]
    for nom, cles in (prod.get("services") or {}).items():
        services.setdefault(nom, {}).update(cles or {})
    return services


class DockerComposeTests(unittest.TestCase):
    def setUp(self):
        self.services = _services()

    def test_services_vitaux_ont_un_healthcheck(self):
        attendus = {
            "db": "pg_isready -h localhost -U $$POSTGRES_USER",
            "redis": "redis-cli",
            "django_core": "http://localhost:8000/api/django/core/health/live/",
        }
        for nom, sonde in attendus.items():
            with self.subTest(service=nom):
                hc = self.services[nom].get("healthcheck")
                self.assertIsNotNone(hc, f"{nom} sans healthcheck")
                self.assertIn(sonde, " ".join(hc["test"]))
                for cle in ("interval", "timeout", "start_period"):
                    self.assertIn(cle, hc)
        self.assertIn("urllib.request", " ".join(self.services["django_core"]["healthcheck"]["test"]))
        self.assertNotIn("health/ready", " ".join(self.services["django_core"]["healthcheck"]["test"]))

    def test_django_attend_base_et_redis_sains(self):
        dep = self.services["django_core"]["depends_on"]
        self.assertEqual(dep["db"]["condition"], "service_healthy")
        self.assertEqual(dep["redis"]["condition"], "service_healthy")

    def test_nginx_sans_condition_de_sante_sur_django(self):
        dep = self.services["nginx"].get("depends_on") or []
        if isinstance(dep, dict):
            self.assertNotEqual((dep.get("django_core") or {}).get("condition"), "service_healthy")


if __name__ == "__main__":
    unittest.main()
