"""Matrice endpoint×rôle canonique (YRBAC2).

Déclare, pour un ensemble d'endpoints métier de référence (crm + ventes +
stock + qhse + gestion_projet + contrats + litiges + kb), le VERDICT attendu
(``ALLOW`` / ``DENY``) par rôle canonique parmi les 7 de
``roles.CANONICAL_SYSTEM_ROLES``. Le test ``core/tests/test_rbac_matrix.py``
crée, par société de test, un utilisateur de chaque rôle et appelle chaque
entrée en asserttant le code HTTP (2xx = allow / 403|404 = deny).

Cette table est la source de vérité du comportement RBAC attendu sur ces
surfaces — un changement de garde qui la contredit casse le test. Elle démarre
sur crm/ventes/stock (apps déjà finement gatées) comme référence verte ;
YRBAC3 l'étend aux 5 apps nouvellement fine-grainées (qhse/gestion_projet/
contrats/litiges/kb — toutes en lecture ``<app>_voir``, désormais accordée aux
7 rôles canoniques y compris Viewer).

``core`` reste FONDATION : ce module ne déclare que des données (chemins,
noms de rôles, verdicts) — aucun import d'app métier.
"""
from __future__ import annotations

from dataclasses import dataclass

ALLOW = "allow"
DENY = "deny"

# Les 7 rôles canoniques système (miroir de roles.CANONICAL_SYSTEM_ROLES, sans
# les 2 rôles légacy). Le test valide que cette liste reste alignée.
CANONICAL_ROLE_NAMES = (
    "Directeur",
    "Administrateur",
    "Commercial responsable",
    "Commercial",
    "Technicien responsable",
    "Technicien",
    "Viewer",
)


@dataclass(frozen=True)
class MatrixEntry:
    """Une ligne de matrice : un endpoint (méthode+chemin) et ses verdicts."""
    app: str
    label: str
    method: str
    path: str
    verdicts: dict  # role_name -> ALLOW|DENY
    # Champ optionnel : payload minimal pour un POST (create).
    body: dict | None = None

    def verdict_for(self, role_name: str) -> str:
        return self.verdicts[role_name]


def _all(verdict: str) -> dict:
    return {name: verdict for name in CANONICAL_ROLE_NAMES}


def _only(*allowed_roles: str) -> dict:
    """ALLOW pour les rôles nommés, DENY pour les autres."""
    return {
        name: (ALLOW if name in allowed_roles else DENY)
        for name in CANONICAL_ROLE_NAMES
    }


# ── Matrice de référence crm + ventes + stock ────────────────────────────────
# NB : ``IsResponsableOrAdmin`` passe pour TOUT porteur de rôle (les 7) ; les
# différenciateurs réels sont ``IsAdminRole`` (Directeur/Administrateur) et
# ``HasPermissionAndRole('stock_creer', Directeur, Commercial responsable)``.

MATRIX: tuple[MatrixEntry, ...] = (
    # ─ CRM ─
    MatrixEntry(
        app="crm", label="Liste des leads",
        method="GET", path="/api/django/crm/leads/",
        verdicts=_all(ALLOW),  # IsAnyRole
    ),
    MatrixEntry(
        app="crm", label="Liste des clients",
        method="GET", path="/api/django/crm/clients/",
        verdicts=_all(ALLOW),
    ),
    # ─ VENTES ─
    MatrixEntry(
        app="ventes", label="Liste des devis",
        method="GET", path="/api/django/ventes/devis/",
        verdicts=_all(ALLOW),  # IsAnyRole
    ),
    MatrixEntry(
        app="ventes", label="Liste des factures",
        method="GET", path="/api/django/ventes/factures/",
        verdicts=_all(ALLOW),
    ),
    # ─ STOCK ─
    MatrixEntry(
        app="stock", label="Liste des produits",
        method="GET", path="/api/django/stock/produits/",
        verdicts=_all(ALLOW),  # IsAnyRole
    ),
    # Différenciateur fort : création de produit réservée à Directeur +
    # Commercial responsable (QG4 — HasPermissionAndRole('stock_creer', …)).
    MatrixEntry(
        app="stock", label="Créer un produit (QG4 gate)",
        method="POST", path="/api/django/stock/produits/",
        verdicts=_only("Directeur", "Commercial responsable"),
        body={"nom": "RBAC-matrix produit", "prix_vente": 100},
    ),
    # ─ QHSE (YRBAC3 — <app>_voir accordé aux 7 rôles canoniques) ─
    MatrixEntry(
        app="qhse", label="Liste des non-conformités",
        method="GET", path="/api/django/qhse/non-conformites/",
        verdicts=_all(ALLOW),  # qhse_voir accordé à tous les 7 rôles.
    ),
    # ─ GESTION_PROJET ─
    MatrixEntry(
        app="gestion_projet", label="Liste des projets",
        method="GET", path="/api/django/gestion-projet/projets/",
        verdicts=_all(ALLOW),  # projet_voir accordé à tous les 7 rôles.
    ),
    # ─ CONTRATS ─
    MatrixEntry(
        app="contrats", label="Liste des contrats",
        method="GET", path="/api/django/contrats/contrats/",
        verdicts=_all(ALLOW),  # contrat_voir accordé à tous les 7 rôles.
    ),
    # ─ LITIGES ─
    MatrixEntry(
        app="litiges", label="Liste des réclamations",
        method="GET", path="/api/django/litiges/reclamations/",
        verdicts=_all(ALLOW),  # litige_voir accordé à tous les 7 rôles.
    ),
    # ─ KB ─
    MatrixEntry(
        app="kb", label="Liste des articles KB",
        method="GET", path="/api/django/kb/articles/",
        verdicts=_all(ALLOW),  # kb_voir accordé à tous les 7 rôles.
    ),
)


def entries_for(app: str) -> list[MatrixEntry]:
    return [e for e in MATRIX if e.app == app]


def covered_apps() -> set[str]:
    return {e.app for e in MATRIX}
