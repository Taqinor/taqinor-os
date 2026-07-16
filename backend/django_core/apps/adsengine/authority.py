"""ADSENG11 — Table d'autorité par barreau, comme DONNÉES (dd-science-core §3).

Le tableau « rung → autorité de décision » du dossier, encodé en **données** (un
dict de module), jamais en logique codée en dur. Les services CHARGENT la table
(éventuellement avec des overrides par société) et la logique la LIT : aucune
fonction ne contient un ``if rung == 'ctr'`` — changer une autorité se fait en
modifiant les données, pas le code (propriété testée).

Le principe (dd-science-core §1.4/§3) : seul le HAUT de l'entonnoir porte de la
puissance statistique, donc seul lui autorise une action AUTONOME ; les barreaux
« argent » (lead qualifié, signature) ne peuvent JAMAIS piloter en autonome —
ils PROPOSENT (approbation humaine) ou INFORMENT seulement.

| Barreau                         | Niveau      | Actions autonomes            |
|---------------------------------|-------------|------------------------------|
| Impression→clic (CTR)           | autonomous  | rebalance_budget             |
| Clic→conversation (proxy)       | autonomous  | rebalance_budget, pause_arm  |
| Conversation→lead qualifié (CRM)| propose     | — (propose-only)             |
| Lead qualifié→signature (CRM)   | inform      | — (inform-only)              |

``promote_challenger`` n'est JAMAIS dans une liste d'actions autonomes : une
activation de créatif/campagne naît toujours PAUSED et son go-live est une
approbation humaine (règle #3). Ce module est PUR : données + résolveurs, aucun
import de modèle. Les identifiants d'action sont les noms « science » (§3),
mappés vers ``EngineAction.Kind`` côté services.
"""
from __future__ import annotations

import copy

# ── Niveaux d'autorité (identifiants anglais). ──────────────────────────────
AUTONOMOUS = 'autonomous'   # écrit une EngineAction auto-approuvée (sous plafond)
PROPOSE = 'propose'         # propose-only : approbation humaine requise
INFORM = 'inform'           # signal seulement (mensuel/trimestriel), jamais d'action

# ── Barreaux de l'entonnoir (identifiants anglais). ─────────────────────────
RUNG_CTR = 'imp_to_click'
RUNG_PROXY = 'click_to_conversation'
RUNG_QUALIFIED = 'conversation_to_qualified'
RUNG_SIGNATURE = 'qualified_to_signature'

# ── Actions « science » (§3) — mappées vers EngineAction.Kind côté services. ─
ACTION_REBALANCE_BUDGET = 'rebalance_budget'
ACTION_PAUSE_ARM = 'pause_arm'
ACTION_PROMOTE_CHALLENGER = 'promote_challenger'   # JAMAIS autonome (règle #3)

# ── La TABLE (données). Modifiable sans toucher au code (via overrides). ─────
AUTHORITY_TABLE = {
    RUNG_CTR: {
        'level': AUTONOMOUS,
        'autonomous_actions': [ACTION_REBALANCE_BUDGET],
        'label_fr': 'Impression→clic (CTR)',
    },
    RUNG_PROXY: {
        'level': AUTONOMOUS,
        'autonomous_actions': [ACTION_REBALANCE_BUDGET, ACTION_PAUSE_ARM],
        'label_fr': 'Clic→conversation (proxy)',
    },
    RUNG_QUALIFIED: {
        'level': PROPOSE,
        'autonomous_actions': [],
        'label_fr': 'Conversation→lead qualifié (CRM)',
    },
    RUNG_SIGNATURE: {
        'level': INFORM,
        'autonomous_actions': [],
        'label_fr': 'Lead qualifié→signature (CRM)',
    },
}


class UnknownRungError(ValueError):
    """Barreau inconnu de la table d'autorité (jamais un défaut silencieux)."""


def load_authority_table(overrides=None):
    """Renvoie une COPIE de la table par défaut, fusionnée avec ``overrides``.

    Les services l'appellent pour charger une configuration (éventuellement
    ajustée par société) SANS modifier le code : ``overrides`` est un dict
    ``rung -> champs à remplacer``. La table par défaut n'est jamais mutée.
    """
    table = copy.deepcopy(AUTHORITY_TABLE)
    for rung, patch in (overrides or {}).items():
        entry = table.get(rung, {})
        entry.update(copy.deepcopy(patch))
        table[rung] = entry
    return table


def get_authority(rung, table=None):
    """Entrée d'autorité d'un barreau (dict). Lève ``UnknownRungError`` sinon —
    jamais de défaut silencieux vers « autonome »."""
    table = AUTHORITY_TABLE if table is None else table
    try:
        return table[rung]
    except KeyError:
        raise UnknownRungError(f"Barreau inconnu : {rung!r}")


def authority_level(rung, table=None):
    """Niveau d'autorité d'un barreau (``autonomous`` / ``propose`` / ``inform``)."""
    return get_authority(rung, table)['level']


def is_autonomous(rung, table=None):
    """Le barreau autorise-t-il une action autonome ? (lit la DONNÉE)."""
    return authority_level(rung, table) == AUTONOMOUS


def is_auto_applicable(rung, action_kind=None, *, within_guardrail=True,
                       table=None):
    """Une action de ce barreau peut-elle être AUTO-appliquée ?

    Vrai uniquement si (a) le barreau est autonome, (b) l'action figure dans ses
    ``autonomous_actions`` (si ``action_kind`` est fourni), et (c) le changement
    reste sous le plafond de garde-fou (``within_guardrail``). Toute autre
    combinaison ⇒ False (l'action devient propose-only). ``promote_challenger``,
    absent de toute liste autonome, est donc TOUJOURS propose (règle #3).
    """
    entry = get_authority(rung, table)
    if entry['level'] != AUTONOMOUS:
        return False
    if action_kind is not None and action_kind not in entry['autonomous_actions']:
        return False
    return bool(within_guardrail)


def requires_proposal(rung, action_kind=None, *, within_guardrail=True,
                      table=None):
    """Négation de :func:`is_auto_applicable` : l'action doit-elle être PROPOSÉE
    (EngineAction ``auto=False``) plutôt qu'auto-appliquée ? Toute action issue
    d'un barreau non-autonome passe par ici (dd-science-core §3)."""
    return not is_auto_applicable(
        rung, action_kind, within_guardrail=within_guardrail, table=table)
