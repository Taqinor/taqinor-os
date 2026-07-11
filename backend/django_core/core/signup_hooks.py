"""SCA20 — Registre de hooks « à la création d'une société » (motif du bus M6).

Le signup d'une nouvelle société (``authentication.views.RegisterCompanyView``)
doit initialiser un jeu de données de départ : rôles système, profil, types
d'activité, niveaux de relance ET — désormais — le CATALOGUE produit. Plutôt
qu'un bloc INLINE monolithique dans la vue (qui ne connaît pas les apps
satellites), chaque app enregistre un CALLABLE idempotent dans ce registre
depuis son ``apps.py`` ``ready()`` (même patron que le bus d'événements M6 :
l'émetteur — ici la vue de signup — ne connaît pas ses abonnés).

Contrat d'un hook :

    def mon_hook(company, *, user=None):
        # Idempotent & additif : rejouable sans créer de doublon.
        ...

``run_signup_hooks(company, user=None)`` exécute TOUS les hooks enregistrés,
best-effort (un hook qui lève est isolé et journalisé — il ne fait jamais
échouer la création de la société ni les autres hooks). L'ordre d'exécution
suit ``priority`` (croissant, défaut 100) puis l'ordre d'enregistrement.

``core`` est une couche de FONDATION : ce registre ne dépend d'AUCUNE app
métier ; les apps s'y branchent (import descendant autorisé).
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Registre : liste de tuples (priority, seq, name, callable).
_HOOKS: list = []
_SEQ = 0


def register_signup_hook(name, fn, *, priority=100):
    """Enregistre (idempotent par ``name``) un hook « nouvelle société ».

    Réenregistrer le même ``name`` REMPLACE le callable précédent (utile au
    rechargement en tests/dev) — jamais de doublon d'exécution."""
    global _SEQ
    if not name or not callable(fn):
        raise ValueError('register_signup_hook : nom + callable requis.')
    # Retire un enregistrement homonyme préexistant (remplacement idempotent).
    _HOOKS[:] = [h for h in _HOOKS if h[2] != name]
    _HOOKS.append((priority, _SEQ, name, fn))
    _SEQ += 1


def registered_hooks():
    """Noms des hooks enregistrés, dans l'ordre d'exécution (rendu stable)."""
    return [h[2] for h in sorted(_HOOKS, key=lambda h: (h[0], h[1]))]


def run_signup_hooks(company, user=None):
    """Exécute tous les hooks enregistrés pour ``company`` (best-effort).

    Renvoie ``{name: 'ok'|'erreur: ...'}``. Un hook qui lève est isolé : il
    n'interrompt ni la création de la société ni les autres hooks."""
    resultats = {}
    for _prio, _seq, name, fn in sorted(_HOOKS, key=lambda h: (h[0], h[1])):
        try:
            fn(company, user=user)
            resultats[name] = 'ok'
        except Exception as exc:  # noqa: BLE001 — un hook KO n'arrête jamais tout
            logger.warning('signup hook %s a échoué: %s', name, exc,
                           exc_info=True)
            resultats[name] = f'erreur: {exc}'
    return resultats


# ---------------------------------------------------------------------------
# SCA28 — hook « branding neutre » de core (thème + modèles brandés par défaut).
#
# ``core`` étant lui-même une couche de fondation qui PORTE les modèles
# ``TenantTheme``/``BrandedTemplate``, il enregistre son propre hook de seed
# (contrairement à stock/authentication qui le font depuis LEUR ``apps.py``).
# Le seed vit dans ``core.services`` ; ce hook n'est qu'un adaptateur mince vers
# ``run_signup_hooks``. Idempotent + best-effort (isolé par ``run_signup_hooks``).
# ---------------------------------------------------------------------------


def seed_branding_hook(company, *, user=None):
    """Seed le thème neutre + les modèles brandés par défaut (idempotent)."""
    from core.services import seed_tenant_branding
    seed_tenant_branding(company, user=user)


def register_core_signup_hooks():
    """Branche le hook de branding neutre au registre (idempotent).

    Appelé depuis ``core.apps.CoreConfig.ready()``. Le ré-enregistrement remplace
    (jamais de doublon d'exécution). Priorité 30 : après les rôles/profil INLINE
    de la vue, aux côtés des seeds satellites (types d'activité / relance)."""
    register_signup_hook('branding', seed_branding_hook, priority=30)
