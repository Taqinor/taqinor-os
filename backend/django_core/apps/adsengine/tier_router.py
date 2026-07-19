"""AGEN6 — Routeur des paliers A/B/C + graduation (pattern toggle ENG8).

dd-assumption-engine §10.1 : trois paliers de génération.
  * **Palier A — automatique jour 1** : tout est vert (chiffres whitelistés
    AGEN3, ancrage AGEN4, policy AGEN5) ET le gabarit est DÉJÀ gradué → l'asset
    file droit au backlog.
  * **Palier B — généré seul, regardé 10 min/semaine** : tout le reste → lot
    hebdomadaire (revue humaine). Graduable en A après N semaines propres
    (toggle PAR capacité).
  * **Palier C — jamais** : types structurellement interdits (chantiers/clients/
    témoignages réels, tout chiffre hors table). INVARIANT : jamais généré.

La graduation est un **toggle par gabarit**, adossé au CACHE (pas de champ
modèle, donc pas de migration — exactement le contrat de cette lane) : défaut
OFF, activable après ``CLEAN_WEEKS_FOR_GRADUATION`` semaines propres, et
RÉVOCABLE (rollback/quarantaine AGEN9). Le routeur CONSOMME les verdicts
d'AGEN3/4/5 ; il ne re-vérifie rien.
"""
from __future__ import annotations

from django.core.cache import cache

from . import groundedness

# ── Paliers ──────────────────────────────────────────────────────────────────
TIER_A = 'A'
TIER_B = 'B'
TIER_C = 'C'

# ── Config (la ligne « N semaines propres » vit ici, pas en dur ailleurs) ─────
CLEAN_WEEKS_FOR_GRADUATION = 3

# Palier C — types de contenu STRUCTURELLEMENT interdits (dd §10.1). Jamais
# générés, jamais gradables. (Config : éditable sans toucher au moteur.)
FORBIDDEN_C_TYPES = frozenset({
    'temoignage_reel',    # témoignage d'un vrai client
    'client_reel',        # visage/nom d'un vrai client
    'chantier_reel',      # photo d'un vrai chantier Taqinor
    'chiffre_hors_table',  # tout chiffre hors table de faits
})

# Clés de cache (préfixées société — pas de fuite cross-tenant).
_GRAD_PREFIX = 'adsengine:graduation'
_CLEAN_PREFIX = 'adsengine:clean_weeks'


def _cid(company):
    return getattr(company, 'id', company) or 0


def _grad_key(company, template_id):
    return f'{_GRAD_PREFIX}:{_cid(company)}:{template_id}'


def _clean_key(company, template_id):
    return f'{_CLEAN_PREFIX}:{_cid(company)}:{template_id}'


# ── Graduation (toggle par gabarit, cache-backed, défaut OFF) ─────────────────
def template_graduated(company, template_id):
    """Vrai si le gabarit est gradué en Palier A. Défaut OFF (pas de clé)."""
    if not template_id:
        return False
    return bool(cache.get(_grad_key(company, template_id), False))


def set_template_graduated(company, template_id, graduated=True):
    """Active/désactive explicitement la graduation d'un gabarit (persistant)."""
    cache.set(_grad_key(company, template_id), bool(graduated), None)
    return bool(graduated)


def revoke_graduation(company, template_id):
    """Révoque la graduation (rollback/quarantaine AGEN9) et remet le compteur
    de semaines propres à zéro — le gabarit repart en Palier B."""
    set_template_graduated(company, template_id, False)
    cache.set(_clean_key(company, template_id), 0, None)


def clean_weeks(company, template_id):
    """Nombre de semaines propres consécutives enregistrées pour le gabarit."""
    return int(cache.get(_clean_key(company, template_id), 0) or 0)


def record_clean_week(company, template_id):
    """Enregistre une semaine propre ; gradue automatiquement au seuil.

    Renvoie le compteur courant. À ``CLEAN_WEEKS_FOR_GRADUATION`` → graduation
    activée (le gabarit devient éligible Palier A)."""
    n = clean_weeks(company, template_id) + 1
    cache.set(_clean_key(company, template_id), n, None)
    if n >= CLEAN_WEEKS_FOR_GRADUATION:
        set_template_graduated(company, template_id, True)
    return n


def is_forbidden_type(content_type):
    """Vrai si le type de contenu est un Palier C (jamais généré)."""
    return content_type in FORBIDDEN_C_TYPES


# ── Routage ───────────────────────────────────────────────────────────────────
def route_tier(company, *, content_type=None, claim_result=None,
               groundedness_result=None, policy_result=None, template_id=None):
    """Décide le palier A/B/C d'une variante à partir des verdicts AGEN3/4/5.

    Renvoie ``{tier, all_green, graduated, reason, checks}``.

    INVARIANT : un ``content_type`` de ``FORBIDDEN_C_TYPES`` renvoie TOUJOURS
    ``C`` — quels que soient les verdicts, il n'est jamais routé vers A ni B
    (et ne doit jamais être généré en amont).
    """
    if is_forbidden_type(content_type):
        return {
            'tier': TIER_C,
            'all_green': False,
            'graduated': False,
            'reason': (f'Type « {content_type} » structurellement interdit '
                       f'(Palier C) — jamais généré.'),
            'checks': {},
        }

    claim_ok = bool(claim_result and claim_result.get('ok'))
    policy_ok = bool(policy_result and policy_result.get('ok'))
    grounded_ok = bool(
        groundedness_result
        and groundedness_result.get('tier') == groundedness.TIER_A)
    checks = {
        'claim_ok': claim_ok,
        'policy_ok': policy_ok,
        'groundedness_ok': grounded_ok,
    }
    all_green = claim_ok and policy_ok and grounded_ok
    graduated = template_graduated(company, template_id)

    if all_green and graduated:
        return {
            'tier': TIER_A,
            'all_green': True,
            'graduated': True,
            'reason': ('Tout vert ET gabarit gradué → Palier A (backlog '
                       'direct).'),
            'checks': checks,
        }

    if not all_green:
        failed = [k for k, v in checks.items() if not v]
        reason = (f'Palier B — vérifs non vertes : {", ".join(failed)}.')
    else:
        reason = ('Palier B — tout vert mais gabarit non gradué (attend '
                  f'{CLEAN_WEEKS_FOR_GRADUATION} semaines propres).')
    return {
        'tier': TIER_B,
        'all_green': all_green,
        'graduated': graduated,
        'reason': reason,
        'checks': checks,
    }
