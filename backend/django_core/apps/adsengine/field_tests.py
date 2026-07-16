"""ADSENG37 — Les 7 inconnues terrain, en CONSTANTES DE CONFIG (pas en dur).

Certaines mécaniques Meta ne se tranchent QUE sur le compte réel (dd-meta-mechanics
§j) : ni la doc ni la recherche ne les fixent. On les traite comme des
**constantes de configuration** avec :

  * une ``value`` = la meilleure estimation actuelle (issue de la RECHERCHE,
    marquée ``SOURCE_RESEARCH`` = NON vérifiée sur le compte) ;
  * un ``source`` qui passe à ``SOURCE_FIELD_TEST`` UNIQUEMENT quand un micro-test
    réel (runbook ``docs/engine/field-tests.md``) l'a confirmée — on met alors à
    jour ``value`` ICI, jamais un littéral en dur ailleurs dans le moteur.

Ainsi, le jour où un test terrain répond, le changement se fait en UN endroit
(cette table) et tout le moteur en hérite — jamais une valeur magique dispersée.

Les 7 inconnues (= les 7 micro-tests FT1..FT7 du runbook) :

  FT1 — seuils exacts de reset d'apprentissage (budget %, conversions) ;
  FT2 — viabilité d'un split-test à petit budget (budget minimum réel) ;
  FT3 — défauts des enhancements Advantage+ (enroll_status par flag) ;
  FT4 — granularité du reporting DCO (par asset vs par ad) ;
  FT5 — coûts réels du Business-Use-Case (points lecture vs écriture) ;
  FT6 — rotation intra-ad-set (« Even Rotation » encore réglable par API ?) ;
  FT7 — gating par palier d'accès (adrules_library / ad_studies).
"""
from __future__ import annotations

# ── Provenance d'une valeur ───────────────────────────────────────────────────
SOURCE_RESEARCH = 'research'      # borne documentaire — NON vérifiée sur le compte
SOURCE_FIELD_TEST = 'field_test'  # confirmée par un micro-test réel (runbook)

# ── Garde-fous du protocole de micro-test (SÛRS — jamais un budget réel large) ─
# Tout micro-test terrain : budget PLAFONNÉ, structures PAUSED d'abord (règle #3),
# un seul facteur changé à la fois. Ce sont des CONSTANTES de config (lisibles par
# le runbook / un futur lanceur de micro-test), jamais des littéraux en dur.
MICRO_TEST_MAX_DAILY_BUDGET_MAD = 30   # plafond dur d'un micro-test terrain
MICRO_TEST_START_PAUSED = True         # toute structure de test naît PAUSED
MICRO_TEST_ONE_FACTOR_AT_A_TIME = True  # un seul facteur changé par test


# ── La table des 7 inconnues (le seed de config, façon STAGES.py) ─────────────
# Chaque entrée : ``value`` (estimation courante), ``unit``, ``source``,
# ``ft`` (micro-test qui la tranche), ``label_fr`` (libellé humain),
# ``consumer`` (module moteur qui la lit — traçabilité du câblage).
CONSTANTS = {
    # FT1 — seuils de reset d'apprentissage.
    'learning_reset_budget_pct': {
        'value': 20, 'unit': '%', 'source': SOURCE_RESEARCH, 'ft': 'FT1',
        'label_fr': "Variation de budget qui reset l'apprentissage",
        'consumer': 'budget_applier',
    },
    'learning_reset_conversions': {
        'value': 50, 'unit': 'conversions/7 j', 'source': SOURCE_RESEARCH,
        'ft': 'FT1', 'label_fr': "Conversions/7 j pour sortir de l'apprentissage",
        'consumer': 'pacing',
    },
    # FT2 — viabilité d'un split-test à petit budget.
    'split_test_min_budget_mad': {
        'value': 200, 'unit': 'MAD/jour/variante', 'source': SOURCE_RESEARCH,
        'ft': 'FT2',
        'label_fr': "Budget minimum d'un split-test natif non dégénéré",
        'consumer': 'flightplan',
    },
    # FT3 — défauts des enhancements créatifs Advantage+.
    'advantage_enhancement_default_on': {
        'value': True, 'unit': 'bool', 'source': SOURCE_RESEARCH, 'ft': 'FT3',
        'label_fr': "Enhancements Advantage+ activés par défaut (à forcer OFF)",
        'consumer': 'launch_templates',
    },
    # FT4 — granularité du reporting DCO.
    'dco_reporting_granularity': {
        'value': None, 'unit': 'par_asset|par_ad', 'source': SOURCE_RESEARCH,
        'ft': 'FT4', 'label_fr': "Granularité du reporting DCO (asset vs ad)",
        'consumer': 'reporting',
    },
    # FT5 — coûts réels du Business-Use-Case (rate limiting).
    'buc_read_cost_points': {
        'value': 1, 'unit': 'points', 'source': SOURCE_RESEARCH, 'ft': 'FT5',
        'label_fr': "Coût BUC d'un appel LECTURE",
        'consumer': 'meta_client',
    },
    'buc_write_cost_points': {
        'value': 3, 'unit': 'points', 'source': SOURCE_RESEARCH, 'ft': 'FT5',
        'label_fr': "Coût BUC d'un appel ÉCRITURE",
        'consumer': 'meta_client',
    },
    # FT6 — rotation intra-ad-set (« Even Rotation »).
    'even_rotation_api_settable': {
        'value': None, 'unit': 'bool', 'source': SOURCE_RESEARCH, 'ft': 'FT6',
        'label_fr': "« Even Rotation » entre ads d'un ad set réglable par API",
        'consumer': 'rotation',
    },
    # FT7 — gating par palier d'accès.
    'access_tier_gates_rules_library': {
        'value': None, 'unit': 'bool', 'source': SOURCE_RESEARCH, 'ft': 'FT7',
        'label_fr': "adrules_library gaté par le palier de vérification business",
        'consumer': 'rules_engine',
    },
    'access_tier_gates_ad_studies': {
        'value': None, 'unit': 'bool', 'source': SOURCE_RESEARCH, 'ft': 'FT7',
        'label_fr': "ad_studies gaté par le palier de vérification business",
        'consumer': 'flightplan',
    },
}

# Les 7 micro-tests (identifiants) — la garde du test aligne cette liste sur le
# runbook + sur les ``ft`` déclarés dans ``CONSTANTS``.
FIELD_TESTS = ('FT1', 'FT2', 'FT3', 'FT4', 'FT5', 'FT6', 'FT7')


def value(key):
    """Valeur courante d'une constante terrain (``KeyError`` si inconnue)."""
    return CONSTANTS[key]['value']


def source(key):
    """Provenance de la valeur (``research`` tant qu'aucun test ne l'a confirmée)."""
    return CONSTANTS[key]['source']


def is_field_tested(key):
    """Vrai UNIQUEMENT si un micro-test réel a confirmé la valeur."""
    return CONSTANTS[key]['source'] == SOURCE_FIELD_TEST


def pending_keys():
    """Constantes encore NON vérifiées terrain (source = recherche) — la liste
    des inconnues qu'un futur passage sur le compte réel doit trancher."""
    return sorted(k for k, c in CONSTANTS.items()
                  if c['source'] == SOURCE_RESEARCH)


def constants_for(ft):
    """Constantes qu'un micro-test donné (``FT1``..``FT7``) doit résoudre."""
    return sorted(k for k, c in CONSTANTS.items() if c['ft'] == ft)


def micro_test_budget_cap_mad():
    """Plafond de budget d'un micro-test terrain — lu depuis la config (jamais un
    littéral en dur chez l'appelant)."""
    return MICRO_TEST_MAX_DAILY_BUDGET_MAD
