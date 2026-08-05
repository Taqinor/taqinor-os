"""NTADM7 — plans de licence par tenant. EXTENSION de FG391
(``core.feature_flags``), jamais un doublon : ``core.feature_flags.module_actif``
reste le SEUL interrupteur ON/OFF par société (``ModuleToggle``). Cette couche
ajoute un DEUXIÈME axe, orthogonal : le PALIER de licence auquel la société
est abonnée (``CompanyProfile.plan`` → ``adminops.PlanLicence``) borne quels
modules le palier INCLUT. ``core`` reste une couche de fondation (contrat
import-linter ``core-foundation-is-a-base-layer``, aucun import d'app
métier) : cette logique vit donc dans ``apps.parametres`` (qui possède déjà
``CompanyProfile``), jamais dans ``core``.

FONDATION SEULE (NTADM7) : rien n'appelle encore ``has_feature`` pour masquer
la nav ou bloquer un endpoint — ce câblage reste sur FG391/ODX (nav masking),
jamais dupliqué ici. Politique NON-RESTRICTIVE PAR DÉFAUT : une société sans
plan (``CompanyProfile.plan`` NULL, le cas de TOUTE société existante
aujourd'hui) voit ``has_feature`` renvoyer ``True`` pour n'importe quel
module — zéro régression tant qu'aucun plan n'est explicitement assigné
(assignation réservée au founder, admin Django).
"""
from __future__ import annotations


def has_feature(company, module_key):
    """Vrai si ``module_key`` est inclus dans le palier de licence de
    ``company``.

    Sans société, sans profil ou sans plan assigné → ``True`` (accès complet,
    comportement actuel préservé). Avec un plan assigné → ``True`` seulement
    si ``module_key`` figure dans ``PlanLicence.modules_inclus`` du palier.
    """
    if company is None:
        return True
    from .models import CompanyProfile
    profile = CompanyProfile.get(company=company)
    plan = getattr(profile, 'plan', None)
    if plan is None:
        return True
    return module_key in (plan.modules_inclus or [])
