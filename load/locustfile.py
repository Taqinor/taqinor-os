"""NTPLT48 — Scénarios de charge Locust pour TAQINOR OS.

Simule un utilisateur ERP typique : connexion (cookie JWT), navigation de la
liste des leads paginée, création de devis, rendu du PDF ``/proposal``,
recherche globale et dashboard. Sert à MESURER la tenue en charge sur la
config Hetzner de référence (seuils dans ``docs/load-testing.md``).

Lancer (jamais contre la prod) ::

    locust -f load/locustfile.py --host http://localhost

Variables d'environnement :
  * ``LOCUST_USER`` / ``LOCUST_PASSWORD`` — identifiants d'un compte de charge
    dédié (jamais un compte réel) ;
  * ``LOCUST_HOST`` — surchargé par ``--host`` si fourni.

Locust est une dépendance DEV uniquement (``requirements-dev.txt``) — jamais
présente dans l'image de production.
"""
import os
import random

try:
    from locust import HttpUser, between, task
except ImportError:  # pragma: no cover - locust est une dép dev optionnelle
    # Permet d'importer/compiler le fichier sans locust installé (CI lint).
    def task(*args, **kwargs):  # noqa: D401 - shim no-op
        def deco(f):
            return f
        return deco if not (args and callable(args[0])) else args[0]

    def between(a, b):  # noqa: D401 - shim no-op
        return (a, b)

    class HttpUser:  # noqa: D401 - shim no-op
        abstract = True


USER = os.environ.get("LOCUST_USER", "charge@taqinor.local")
PASSWORD = os.environ.get("LOCUST_PASSWORD", "charge-password")


class ErpUser(HttpUser):
    """Un utilisateur ERP synthétique qui exerce les chemins chauds."""

    wait_time = between(1, 4)

    def on_start(self):
        """Connexion : pose le cookie JWT réutilisé par les requêtes suivantes."""
        self.client.post(
            "/api/django/auth/login/",
            json={"username": USER, "password": PASSWORD},
            name="auth:login",
        )

    @task(6)
    def liste_leads(self):
        """Liste des leads paginée (chemin de lecture le plus fréquent)."""
        page = random.randint(1, 5)
        self.client.get(
            f"/api/django/crm/leads/?page={page}", name="crm:leads:list")

    @task(3)
    def dashboard(self):
        """Dashboard (agrégats KPI)."""
        self.client.get("/api/django/reporting/dashboard/", name="reporting:dashboard")

    @task(3)
    def recherche_globale(self):
        """Recherche globale (barre de recherche instantanée)."""
        q = random.choice(["sol", "pompe", "devis", "casablanca", "onduleur"])
        self.client.get(
            f"/api/django/reporting/search/?q={q}", name="reporting:search")

    @task(2)
    def creation_devis(self):
        """Création d'un devis minimal (chemin d'écriture)."""
        self.client.post(
            "/api/django/ventes/devis/",
            json={"client_nom": "Charge", "lignes": []},
            name="ventes:devis:create",
        )

    @task(1)
    def rendu_proposal(self):
        """Rendu PDF /proposal du dernier devis listé (chemin le plus lourd)."""
        resp = self.client.get(
            "/api/django/ventes/devis/?page=1", name="ventes:devis:list")
        try:
            data = resp.json()
            results = data.get("results") or data
            devis_id = results[0]["id"] if results else None
        except Exception:  # noqa: BLE001 — réponse inattendue → skip
            devis_id = None
        if devis_id:
            self.client.get(
                f"/api/django/ventes/devis/{devis_id}/proposal/",
                name="ventes:proposal",
            )
