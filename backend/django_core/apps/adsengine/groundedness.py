"""AGEN4 — Filet de véracité NON-numérique (groundedness).

dd-assumption-engine §10.2 point 3 : « Filet de véracité non-numérique
(scoreurs groundedness type HHEM/Lynx) ». Là où AGEN3 (``claim_check``) barre
les chiffres faux, ce module barre les AFFIRMATIONS non chiffrées non ancrées
(un bénéfice inventé, une promesse hors composants approuvés). Un scoreur
type HHEM/Lynx note, dans ``[0, 1]``, à quel point le texte est *entailed* par
un matériau de référence ancré (composants approuvés + sources de la table de
faits).

Contrat de sûreté (comme la fabrique créative) :
  * **key-gated** (``ADSENGINE_GROUNDEDNESS_API_KEY``). **Sans clé et sans
    scoreur injecté, on NE PEUT PAS certifier l'ancrage → TOUT est routé vers le
    Palier B** (revue humaine hebdo) : c'est le comportement CONSERVATEUR par
    défaut, jamais un passage optimiste vers A.
  * scoreur réel injectable (les tests injectent un mock) ; aucune dépendance
    pip nouvelle.
"""
from __future__ import annotations

import logging
import os

from .models import FactTable

logger = logging.getLogger(__name__)

# Clé activant le scoreur réel. Absente → routage Palier B systématique.
GROUNDEDNESS_ENV_KEY = 'ADSENGINE_GROUNDEDNESS_API_KEY'

# Seuil d'entailment au-dessus duquel le texte est jugé ancré (éligible Palier
# A pour la dimension groundedness). Défaut raisonné, surchargeable.
GROUNDEDNESS_THRESHOLD = 0.7

# Paliers de routage renvoyés (consommés par ``tier_router`` / AGEN6).
TIER_A = 'A'
TIER_B = 'B'


def _default_scorer():
    """Scoreur HHEM/Lynx réel — construit UNIQUEMENT si la clé est posée.

    ``None`` sans la clé (⇒ routage B). Le jour où une clé existe, ce chemin
    appellera le scoreur d'entailment ; il reste inerte ici (aucune dépendance,
    aucun endpoint en dur) — les tests injectent un scoreur."""
    if not os.environ.get(GROUNDEDNESS_ENV_KEY):
        return None

    def _scorer(text, references):  # pragma: no cover - chemin réseau réel
        logger.info(
            'groundedness: clé %s présente mais aucun backend câblé — '
            'routage B par prudence.', GROUNDEDNESS_ENV_KEY)
        return None

    return _scorer


def _default_references(company):
    """Matériau de référence ancré d'une société : sources + clés de la table
    de faits publiée (le socle textuel contre lequel on juge l'entailment)."""
    table = FactTable.published_for(company)
    if table is None:
        return []
    refs = []
    for entry in table.entries.all():
        parts = [entry.cle, entry.valeur, entry.unite, entry.source]
        refs.append(' '.join(p for p in parts if p))
    return refs


def score_groundedness(company, text, *, references=None, scorer=None,
                       threshold=None):
    """Note l'ancrage NON-numérique d'un texte ; décide A vs B.

    Renvoie ``{enabled, score, grounded, tier, threshold, reason}``. ``tier`` est
    ``'A'`` uniquement si un scoreur a certifié ``score >= threshold`` ; dans
    TOUS les autres cas (pas de clé, scoreur indisponible, score bas) → ``'B'``.
    """
    thr = GROUNDEDNESS_THRESHOLD if threshold is None else threshold
    scr = scorer if scorer is not None else _default_scorer()

    if scr is None:
        return {
            'enabled': False, 'score': None, 'grounded': False,
            'tier': TIER_B, 'threshold': thr,
            'reason': (f'{GROUNDEDNESS_ENV_KEY} absent — ancrage non vérifiable, '
                       f'routage Palier B par prudence.'),
        }

    refs = references if references is not None else _default_references(company)
    score = scr(text or '', refs)

    if score is None:
        return {
            'enabled': True, 'score': None, 'grounded': False,
            'tier': TIER_B, 'threshold': thr,
            'reason': 'Scoreur indisponible — routage Palier B par prudence.',
        }

    grounded = score >= thr
    return {
        'enabled': True,
        'score': score,
        'grounded': grounded,
        'tier': TIER_A if grounded else TIER_B,
        'threshold': thr,
        'reason': ('Ancré (entailment suffisant).' if grounded else
                   f'Affirmation peu ancrée (score {score:.2f} < {thr:.2f}) — '
                   f'routage Palier B.'),
    }
