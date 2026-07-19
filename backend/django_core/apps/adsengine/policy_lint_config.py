"""AGEN5 — CONFIG du pré-linter policy/marque FR (règles, PAS de logique).

STATUT (PUB25, 2026-07-19) — Consommé par ``policy_lint.py`` (moteur), lui-même
NON CÂBLÉ au pipeline de génération en PRODUCTION : ``generation.
generate_grounded_variants`` (câblé par PUB16) fait sa PROPRE garde d'ancrage
numérique et n'invoque pas encore ``policy_lint``. Pas un doublon (la config des
règles vit ICI, la logique dans ``policy_lint.py``). EN ATTENTE DE : l'insertion
de ``policy_lint`` dans le pipeline ``tier_router``/génération. Prêt + testé ;
jamais mort silencieux.

dd-assumption-engine §10.2 point 4 : « Pré-linter policy/marque FR (UN seul
appel par pub) ». Les RÈGLES vivent ici (données, éditables sans toucher au
moteur ``policy_lint.py``) ; chacune porte un id, une catégorie, une action
(``block`` = refus avant soumission Meta / ``flag`` = drapeau non bloquant),
une raison FR et ses motifs regex.

Catégories couvertes (Meta Advertising Standards + marque Taqinor) :
  * ``superlatifs`` — « meilleur », « n°1 », « leader »… (non prouvables).
  * ``attributs_personnels`` — impliquer qu'on connaît un attribut sensible de
    la personne (religion, santé, orientation, situation financière) — interdit
    par Meta.
  * ``avant_apres`` — visuels/textes « avant / après » (interdits en santé/
    esthétique et déconseillés en général).
  * ``financier`` — financement/crédit/paiement échelonné ⇒ **drapeau catégorie
    spéciale « Financial Products »** (ciblage large forcé) — signalé, non bloqué.
  * ``marque`` — vocabulaire marque proscrit : jamais « assurance décennale »
    revendiquée, jamais un COMPTE d'installations/chantiers/clients affiché.

Ajouter/desserrer une règle = éditer cette liste — aucune reconstruction de
migration, aucun changement de code moteur.
"""
from __future__ import annotations

# Nom de la catégorie spéciale Meta déclenchée par un claim financier.
SPECIAL_CATEGORY_FINANCIAL = 'FINANCIAL_PRODUCTS'

# Chaque règle : id / category / action(block|flag) / severity / reason(FR,
# gabarit avec {match}) / patterns(regex, appliqués en IGNORECASE) /
# special_category(optionnel).
POLICY_RULES = [
    {
        'id': 'superlatif',
        'category': 'superlatifs',
        'action': 'block',
        'severity': 'error',
        'reason': ('Superlatif non prouvable (« {match} ») — Meta et la charte '
                   'marque proscrivent les superlatifs absolus.'),
        'patterns': [
            r'\bmeilleur[es]?\b', r'\bn[°ºo]\s*1\b', r'\bnum[ée]ro\s*1\b',
            r'\ble\s+plus\b', r'\bleader\b', r'\bincomparable\b',
            r'\bimbattable\b', r'\b#\s*1\b',
        ],
    },
    {
        'id': 'attribut_personnel',
        'category': 'attributs_personnels',
        'action': 'block',
        'severity': 'error',
        'reason': ('Attribut personnel sensible impliqué (« {match} ») — Meta '
                   'interdit de sous-entendre qu\'on connaît la religion, la '
                   'santé, l\'orientation ou la situation financière de la '
                   'personne.'),
        'patterns': [
            r'\bparce que vous [êe]tes\b',
            r'\bvous [êe]tes\s+(musulman|chr[ée]tien|juif|malade|'
            r'handicap[ée]|au ch[ôo]mage|endett[ée]|divorc[ée]|c[ée]libataire)',
            r'\bvotre (religion|handicap|maladie|dette)\b',
        ],
    },
    {
        'id': 'avant_apres',
        'category': 'avant_apres',
        'action': 'block',
        'severity': 'error',
        'reason': ('Comparatif « avant / après » (« {match} ») — proscrit '
                   '(résultats non garantis / catégorie sensible).'),
        'patterns': [
            r'\bavant\s*/\s*apr[èe]s\b', r'\bavant[- ]apr[èe]s\b',
            r'\bbefore\s*/?\s*after\b',
        ],
    },
    {
        'id': 'financier',
        'category': 'financier',
        'action': 'flag',
        'severity': 'warning',
        'special_category': SPECIAL_CATEGORY_FINANCIAL,
        'reason': ('Claim financier (« {match} ») — déclenche la catégorie '
                   'spéciale Meta « Financial Products » (ciblage large forcé) : '
                   'drapeau, à valider avant soumission.'),
        'patterns': [
            r'\bfinancement\b', r'\bcr[ée]dit\b', r'\bpr[êe]t\b',
            r'\b0\s*%\s*d[\'’]?apport\b', r'\bpayez?\s+en\s+\d+\s*fois\b',
            r'\bpaiement\s+[ée]chelonn[ée]\b', r'\bmensualit[ée]s?\b',
        ],
    },
    {
        'id': 'marque_decennale',
        'category': 'marque',
        'action': 'block',
        'severity': 'error',
        'reason': ('Vocabulaire marque proscrit (« {match} ») — ne jamais '
                   'revendiquer une assurance décennale.'),
        'patterns': [
            r'\bassur[ance]*\s+d[ée]cennale\b', r'\bd[ée]cennale\b',
            r'\bassur[ée]\s+d[ée]cennale\b',
        ],
    },
    {
        'id': 'marque_compte_installations',
        'category': 'marque',
        'action': 'block',
        'severity': 'error',
        'reason': ('Compte d\'installations/chantiers/clients affiché '
                   '(« {match} ») — proscrit par la charte marque.'),
        'patterns': [
            r'\b\d[\d  .]*\d?\s*(installations?|chantiers?|clients?|'
            r'r[ée]alisations?|projets?)\b',
        ],
    },
]
