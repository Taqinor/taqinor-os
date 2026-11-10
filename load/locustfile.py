"""NTPLT48 — Scénarios de charge Locust pour TAQINOR OS.

Simule un utilisateur ERP typique : connexion (cookie JWT), navigation de la
liste des leads paginée, création de devis, rendu du PDF ``/proposal``,
recherche globale et dashboard. Sert à MESURER la tenue en charge sur la
config Hetzner de référence (seuils dans ``docs/load-testing.md``).

Lancer (jamais contre la prod) ::

    locust -f load/locustfile.py --host http://localhost

Variables d'environnement :
  * ``LOCUST_USER`` / ``LOCUST_PASSWORD`` — NOM D'UTILISATEUR (pas l'e-mail :
    la connexion résout le compte par username) et mot de passe d'un compte de
    charge dédié (jamais un compte réel ; ``scripts/load/creer_compte_charge.py``) ;
  * ``LOCUST_HOST`` — surchargé par ``--host`` si fourni.

Locust est une dépendance DEV uniquement (``requirements-dev.txt``) — jamais
présente dans l'image de production.
"""
import math
import os
import random

try:
    from locust import HttpUser, between, task
except ImportError:  # pragma: no cover - locust est une dép dev optionnelle
    # Permet d'importer/compiler le fichier sans locust installé (CI lint).
    def task(*args, **kwargs):  # noqa: D401 — shim no-op (D-ENF22)
        def deco(f):
            return f
        return deco if not (args and callable(args[0])) else args[0]

    def between(a, b):  # noqa: D401 — shim no-op (D-ENF22)
        return (a, b)

    class HttpUser:  # noqa: D401 — shim no-op (D-ENF22)
        abstract = True


USER = os.environ.get("LOCUST_USER", "charge")
# ADCG73 — taille de page DRF par défaut (50) : la page tirée reste dans les bornes du compte.
TAILLE_PAGE = 50
PASSWORD = os.environ.get("LOCUST_PASSWORD", "charge-password")


class ErpUser(HttpUser):
    """Un utilisateur ERP synthétique qui exerce les chemins chauds."""

    wait_time = between(1, 4)

    client_id = None
    nb_pages = 1

    def on_start(self):
        """Connexion : pose le cookie JWT réutilisé par les requêtes suivantes.

        ENF12 — la route était ``/api/django/auth/login/`` (404 : TOUTES les
        requêtes mesurées étaient des 401, masquées). La connexion est
        ``/api/django/token/`` (cookie httpOnly ``access_token``). Un client
        propre à l'utilisateur virtuel porte ensuite les devis créés.
        """
        self.client.post(
            "/api/django/token/",
            json={"username": USER, "password": PASSWORD},
            name="auth:login",
        )
        # ADCG73 — `unique_together (company, email)` : sans e-mail le client était
        # refusé en 400, donc chaque création de devis (client None) aussi.
        n = random.randint(1, 10**9)
        resp = self.client.post(
            "/api/django/crm/clients/",
            json={"nom": f"Charge {n}", "email": f"charge-{n}@taqinor.local"},
            name="crm:clients:create",
        )
        if resp.status_code == 201:
            self.client_id = resp.json().get("id")

    @task(6)
    def liste_leads(self):
        """Liste des leads paginée (chemin de lecture le plus fréquent)."""
        # ADCG73 — `randint(1, 5)` rendait 404 hors bornes : page dans [1, ceil(count / 50)].
        page = random.randint(1, self.nb_pages)
        resp = self.client.get(
            f"/api/django/crm/leads/?page={page}", name="crm:leads:list")
        try:
            count = resp.json().get("count")
        except (ValueError, AttributeError):
            count = None
        if isinstance(count, int):
            self.nb_pages = max(1, math.ceil(count / TAILLE_PAGE))

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
        # ENF12 — ``client_nom`` est en lecture seule : l'ancien corps rendait
        # 400 à chaque appel. Un devis se crée sur un client (id) + TVA.
        if self.client_id is None:  # client refusé : ne pas mesurer un 400 certain
            return
        self.client.post(
            "/api/django/ventes/devis/",
            json={"client": self.client_id, "taux_tva": "20"},
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
        except (ValueError, LookupError, TypeError, AttributeError):  # réponse inattendue → skip
            devis_id = None
        if devis_id:
            self.client.get(
                f"/api/django/ventes/devis/{devis_id}/proposal/",
                name="ventes:proposal",
            )
