"""NTADM7 — plans de licence par tenant. EXTENSION de FG391
(``core.feature_flags``), jamais un doublon : ``core.feature_flags.module_actif``
reste le SEUL interrupteur ON/OFF par société (``ModuleToggle``). Cette couche
ajoute un DEUXIÈME axe, orthogonal : le PALIER de licence auquel la société
est abonnée (``CompanyProfile.plan`` → ``adminops.PlanLicence``) borne quels
modules le palier INCLUT. ``core`` reste une couche de fondation (contrat
import-linter ``core-foundation-is-a-base-layer``, aucun import d'app
métier) : cette logique vit donc dans ``apps.parametres`` (qui possède déjà
``CompanyProfile``), jamais dans ``core``.

SOL9 (2026-09-02) — CÂBLAGE, fin de la « fondation seule ». ``has_feature`` est
désormais branché sur le MÊME chemin que ``ModuleToggle`` : cette app
s'enregistre dans ``core.feature_flags.register_module_access_check`` (motif du
bus M6 — c'est l'app métier qui se branche, ``core`` n'importe rien). Effet :
un module hors plan est renvoyé en 404 par ``DisabledModuleMiddleware`` ET
disparaît de la nav, puisque ``/auth/me`` sert la même liste
``modules_desactives``. Un seul chemin, donc pas de gating divergent.

Politique NON-RESTRICTIVE PAR DÉFAUT, INCHANGÉE : une société sans plan
(``CompanyProfile.plan`` NULL — le cas de TOUTE société existante aujourd'hui)
voit ``has_feature`` renvoyer ``True`` pour n'importe quel module ; zéro
régression tant qu'aucun plan n'est explicitement assigné (assignation
réservée au founder, admin Django). Seuls les modules INSTALLABLES sont bornés
par un plan : jamais une couche de fondation (roles, parametres, core…), ni une
clé sans manifeste.
"""
from __future__ import annotations


def _plan_effectif(profile):
    """APAR55 — palier qui BORNE réellement les modules, ou ``None``.

    Repli documenté « pas de plan » (accès complet) quand le palier est
    INACTIF (``actif=False``) ou VIDE (``modules_inclus`` sans aucune clé) :
    désactiver ou vider un palier dans l'admin ne doit jamais verrouiller en
    silence tous les modules des sociétés qui y sont rattachées."""
    plan = getattr(profile, 'plan', None)
    if plan is None or not getattr(plan, 'actif', True):
        return None
    if not (plan.modules_inclus or []):
        return None
    return plan


def has_feature(company, module_key):
    """Vrai si ``module_key`` est inclus dans le palier de licence de
    ``company``.

    Sans société, sans profil, sans plan assigné, ou palier inactif/vide
    (APAR55) → ``True`` (accès complet, comportement actuel préservé). Avec un plan assigné → ``True`` seulement
    si ``module_key`` figure dans ``PlanLicence.modules_inclus`` du palier.
    """
    if company is None:
        return True
    from .models import CompanyProfile
    # Lecture PURE : jamais ``CompanyProfile.get`` (get-or-CREATE) — un simple
    # contrôle de flag ne doit pas écrire une ligne en effet de bord.
    profile = CompanyProfile.objects.filter(company=company).first()
    plan = _plan_effectif(profile)
    if plan is None:
        return True
    return module_key in (plan.modules_inclus or [])


# ---------------------------------------------------------------------------
# SOL9 — branchement sur le chemin unique de `core.feature_flags`
# ---------------------------------------------------------------------------

def modules_installables():
    """Clés de module INSTALLABLES (les seules qu'un plan puisse borner).

    Public : lu aussi par la validation de ``modules_inclus`` dans l'admin des
    paliers (APAR55, ``apps.adminops.admin.PlanLicenceAdminForm``)."""
    return _modules_installables()


def _modules_installables():
    """Clés de module INSTALLABLES (les seules qu'un plan puisse borner)."""
    from core import modules as modules_infra
    try:
        manifests = modules_infra.collect_manifests()
    except Exception:  # noqa: BLE001 — jamais enfermer un tenant
        return set()
    return {
        key for key, manifest in manifests.items()
        if manifest.get('installable')
    }


def module_dans_le_plan(company, module_key):
    """Vérificateur UNITAIRE (chemin middleware : un appel par requête).

    Une clé de FONDATION (``installable=False``) ou SANS manifeste n'est jamais
    bornée par un plan — un palier commercial ne coupe pas ``roles`` ni une
    surface purement frontend.
    """
    if module_key not in _modules_installables():
        return True
    return has_feature(company, module_key)


def modules_hors_plan(company):
    """Vérificateur GROUPÉ : modules installables exclus du plan, en 1 requête.

    Utilisé par ``/auth/me`` (qui interroge ~70 modules) — sans lui, ce serait
    une requête SQL par module.
    """
    if company is None:
        return set()
    from .models import CompanyProfile
    profile = CompanyProfile.objects.filter(company=company).first()
    plan = _plan_effectif(profile)
    if plan is None:
        return set()          # aucun plan (ou palier inactif/vide) ⇒ accès complet
    inclus = set(plan.modules_inclus or [])
    return {k for k in _modules_installables() if k not in inclus}


def register_plan_access_check():
    """Branche le plan de licence au chemin d'accès unique (idempotent)."""
    from core.feature_flags import register_module_access_check

    register_module_access_check(
        'plan_licence', module_dans_le_plan, exclus=modules_hors_plan)
