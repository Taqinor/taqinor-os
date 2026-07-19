"""AGEN5 — Pré-linter policy/marque FR (moteur ; règles dans la CONFIG).

dd-assumption-engine §10.2 point 4 : « Pré-linter policy/marque FR (UN seul
appel par pub) ». Avant TOUTE soumission Meta, on passe le texte d'une pub au
crible des règles de ``policy_lint_config.POLICY_RULES`` : superlatifs,
attributs personnels sensibles, avant/après, claims financiers (drapeau
catégorie spéciale), vocabulaire marque proscrit. La LOGIQUE est ici, les
RÈGLES sont en config (éditables sans toucher au moteur).

Un flag ``action='block'`` ⇒ le texte n'est PAS soumissible (``ok=False``).
Un flag ``action='flag'`` (ex. financier) ⇒ drapeau non bloquant + catégorie
spéciale à porter dans la soumission. Aucune dépendance pip, aucune migration.
"""
from __future__ import annotations

import re

from .policy_lint_config import POLICY_RULES

# Compilation une seule fois (regex IGNORECASE + UNICODE pour les accents FR).
_COMPILED = [
    {
        'rule': rule,
        'patterns': [re.compile(p, re.IGNORECASE | re.UNICODE)
                     for p in rule['patterns']],
    }
    for rule in POLICY_RULES
]


def lint_text(text, *, rules=None):
    """Passe ``text`` au crible ; renvoie
    ``{ok, flags[], blocking[], special_categories[]}``.

    * ``flags`` : tous les déclenchements (bloquants ET drapeaux), chacun avec
      ``rule_id/category/action/severity/match/reason``.
    * ``ok`` : vrai seulement si AUCUN flag ``action='block'``.
    * ``special_categories`` : catégories spéciales Meta déclenchées (ex.
      ``FINANCIAL_PRODUCTS``).
    ``rules`` permet d'injecter un jeu de règles compilé de test.
    """
    compiled = rules if rules is not None else _COMPILED
    text = text or ''

    flags = []
    special = []
    for item in compiled:
        rule = item['rule']
        for pattern in item['patterns']:
            m = pattern.search(text)
            if not m:
                continue
            match_str = m.group(0)
            flags.append({
                'rule_id': rule['id'],
                'category': rule['category'],
                'action': rule['action'],
                'severity': rule['severity'],
                'match': match_str,
                'reason': rule['reason'].format(match=match_str),
            })
            sc = rule.get('special_category')
            if sc and sc not in special:
                special.append(sc)
            break  # un déclenchement par règle suffit

    blocking = [f for f in flags if f['action'] == 'block']
    return {
        'ok': not blocking,
        'flags': flags,
        'blocking': blocking,
        'special_categories': special,
    }


def lint_asset(asset):
    """Lint hook + texte principal + CTA d'un ``CreativeAsset``."""
    text = ' '.join(filter(None, [
        asset.hook_text, asset.primary_text, asset.cta]))
    return lint_text(text)
