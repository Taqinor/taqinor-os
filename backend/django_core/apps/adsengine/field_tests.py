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


# ── PUB128 — PROTOCOLE de chaque micro-test (config servie à l'écran) ─────────
# Condensé FIDÈLE du runbook ``docs/engine/field-tests.md`` (qui reste le document
# de référence, avec ses bornes de recherche) : l'écran « Tests terrain » sert
# CETTE table, un écran n'ayant pas à parser du markdown. Rien n'est inventé ici —
# chaque étape est celle du runbook, et aucune mécanique Meta n'est AFFIRMÉE (c'est
# précisément ce que le test mesure). Modifier un protocole = éditer les DEUX
# (cette table et le runbook), jamais un littéral dans une vue ou un écran.
PROTOCOLS = {
    'FT1': {
        'label_fr': "Seuils exacts de reset d'apprentissage",
        'question_fr': (
            "Quel % de variation de budget, et combien de conversions sur 7 j, "
            "(re)déclenchent la phase d'apprentissage ?"),
        'protocol_fr': [
            "Créer 1 campagne + 1 ad set PAUSED, budget sous le plafond de "
            "micro-test, une seule ad.",
            "Unpause à la main ; laisser l'ad set SORTIR de l'apprentissage.",
            "Appliquer UNE hausse de budget de +10 % ; observer le label "
            "« Apprentissage » avant / après.",
            "Répéter à +15 % puis +25 % (un seul facteur à la fois) pour "
            "encadrer le vrai seuil.",
            "Repauser à la main.",
        ],
        'measure_fr': (
            "Le plus petit % de hausse qui fait réapparaître le label "
            "« Apprentissage » (et le nombre de conversions/7 j observé à la "
            "sortie d'apprentissage)."),
    },
    'FT2': {
        'label_fr': "Viabilité d'un split-test à petit budget",
        'question_fr': (
            "Quel budget minimum réel faut-il pour qu'un split-test natif rende "
            "un résultat NON dégénéré ?"),
        'protocol_fr': [
            "Lancer UN split-test natif au budget réel (structures PAUSED puis "
            "unpause humain) sur 2 semaines.",
            "Lire les chiffres de puissance / confiance que Meta rapporte "
            "lui-même.",
        ],
        'measure_fr': (
            "Le budget quotidien par variante au-dessus duquel Meta rend un "
            "résultat exploitable — donc « l'outil est-il utilisable à notre "
            "échelle ? »."),
    },
    'FT3': {
        'label_fr': 'Défauts des enhancements créatifs Advantage+',
        'question_fr': (
            "Quel est l'état par défaut de chaque enhancement créatif quand on "
            "ne le déclare pas (politique no-fake-footage : tout enhancement "
            "doit être forcé OFF) ?"),
        'protocol_fr': [
            "Créer UN créatif PAUSED en OMETTANT la spec d'enhancements.",
            "Relire l'objet créé et inspecter ce que Meta a supposé "
            "(statut d'enrôlement par drapeau).",
        ],
        'measure_fr': (
            "Les défauts réels par drapeau : au moins un enhancement revient-il "
            "activé sans l'avoir demandé ? (liste collée en preuve)"),
    },
    'FT4': {
        'label_fr': 'Granularité du reporting DCO',
        'question_fr': (
            "Le reporting DCO remonte-t-il par ASSET ou seulement par AD (donc "
            "l'attribution par variante reste-t-elle fiable sous DCO) ?"),
        'protocol_fr': [
            "Activer le créatif dynamique sur UNE ad de test (PAUSED puis "
            "unpause humain, budget sous le plafond).",
            "Lire les insights et vérifier la présence d'une ventilation par "
            "asset.",
        ],
        'measure_fr': "« par_asset » ou « par_ad ».",
    },
    'FT5': {
        'label_fr': 'Coûts réels du Business-Use-Case (rate limiting)',
        'question_fr': (
            "Quel est le vrai barème de points BUC : combien coûte un appel de "
            "LECTURE, combien un appel d'ÉCRITURE ?"),
        'protocol_fr': [
            "Relever l'en-tête d'usage BUC après UN appel de lecture réel.",
            "Recommencer après UN appel d'écriture réel (une création PAUSED "
            "suffit).",
        ],
        'measure_fr': (
            "Les deux coûts en points observés, en-têtes collés en preuve."),
    },
    'FT6': {
        'label_fr': "Rotation intra-ad-set (« Even Rotation »)",
        'question_fr': (
            "La rotation égale entre plusieurs ads d'un même ad set est-elle "
            "encore un réglage accessible par API ?"),
        'protocol_fr': [
            "Créer 2 ads dans UN ad set SANS toucher au réglage de rotation "
            "(PAUSED puis unpause humain, budget sous le plafond).",
            "Observer sur quelques jours si la dépense se répartit également ou "
            "se concentre sur une seule ad.",
        ],
        'measure_fr': (
            "Vrai/faux, avec la répartition observée (ou le message d'erreur "
            "exact) en preuve."),
    },
    'FT7': {
        'label_fr': "Gating par palier d'accès (vérification business)",
        'question_fr': (
            "Le palier de vérification business gate-t-il spécifiquement la "
            "bibliothèque de règles ou les études A/B natives ?"),
        'protocol_fr': [
            "Tenter UN appel sur l'edge de la bibliothèque de règles du compte.",
            "Tenter UN appel sur l'edge des études A/B natives.",
            "Consigner, pour chacun, s'il réussit au palier courant.",
        ],
        'measure_fr': (
            "Vrai/faux par edge, code d'erreur exact collé en preuve."),
    },
}


def value(key):
    """Valeur courante d'une constante terrain (``KeyError`` si inconnue)."""
    return CONSTANTS[key]['value']


def source(key):
    """Provenance de la valeur (``research`` tant qu'aucun test ne l'a confirmée)."""
    return CONSTANTS[key]['source']


def is_field_tested(key):
    """Vrai UNIQUEMENT si un micro-test réel a confirmé la valeur."""
    return CONSTANTS[key]['source'] == SOURCE_FIELD_TEST


def settled_tests(company=None):
    """PUB128 — Micro-tests TRANCHÉS pour une société (lecture DB).

    Un ``FieldTestResult`` enregistré pour ``FT<n>`` tranche ce micro-test — donc
    toutes les constantes qu'il résout. Sans société (appel pur, hors requête),
    renvoie un ensemble VIDE : les constantes restent alors la seule source."""
    if company is None:
        return frozenset()
    from .models import FieldTestResult
    return frozenset(
        FieldTestResult.objects
        .filter(company=company)
        .values_list('ft', flat=True))


def pending_keys(company=None):
    """Constantes encore NON tranchées — la liste des inconnues qu'un passage sur
    le compte réel doit trancher.

    PUB128 — la DB est consultée D'ABORD : une constante dont le micro-test porte
    un ``FieldTestResult`` pour cette société est tranchée, même si la valeur en
    dur est encore marquée ``SOURCE_RESEARCH`` (l'edit de code n'est plus le seul
    chemin). Les constantes restent le REPLI : sans société, ou pour un test sans
    résultat enregistré, c'est leur ``source`` qui décide."""
    settled = settled_tests(company)
    return sorted(k for k, c in CONSTANTS.items()
                  if c['source'] == SOURCE_RESEARCH and c['ft'] not in settled)


def constants_for(ft):
    """Constantes qu'un micro-test donné (``FT1``..``FT7``) doit résoudre."""
    return sorted(k for k, c in CONSTANTS.items() if c['ft'] == ft)


def micro_test_budget_cap_mad():
    """Plafond de budget d'un micro-test terrain — lu depuis la config (jamais un
    littéral en dur chez l'appelant)."""
    return MICRO_TEST_MAX_DAILY_BUDGET_MAD


def protocol_for(ft):
    """PUB128 — Protocole d'un micro-test (``{label_fr, question_fr,
    protocol_fr, measure_fr}``), ou ``None`` si le test est inconnu. C'est la
    source que sert l'écran « Tests terrain » et depuis laquelle le runbook
    ``docs/engine/field-tests.md`` est rédigé."""
    return PROTOCOLS.get(ft)


def record_result(company, ft, *, measured_value, evidence='',
                  measured_on=None, user=None):
    """PUB128 — Enregistre (ou met à jour) le résultat MESURÉ d'un micro-test.

    Un seul verdict par ``(société, micro-test)`` : ré-enregistrer MET À JOUR.
    Lève ``ValueError`` (raison FR) sur un ``ft`` hors des 7 ou une valeur vide —
    une porte de préflight ne se ferme jamais sur une mesure fantôme."""
    import datetime as _datetime

    from .models import FieldTestResult

    key = str(ft or '').strip().upper()
    if key not in FIELD_TESTS:
        raise ValueError(
            f"Micro-test inconnu « {ft} » : attendu l'un de "
            f"{', '.join(FIELD_TESTS)}.")
    value = str(measured_value or '').strip()
    if not value:
        raise ValueError(
            "La valeur mesurée est obligatoire : la porte de préflight ne se "
            "ferme jamais sur une mesure vide.")
    result, _created = FieldTestResult.objects.update_or_create(
        company=company, ft=key,
        defaults={
            'measured_value': value,
            'evidence': str(evidence or '').strip(),
            'measured_on': measured_on or _datetime.date.today(),
            'recorded_by': user if getattr(user, 'pk', None) else None,
        })
    return result


def propose_micro_test_structures(company, ft, *, city='', proposed_by=None,
                                  template_key='resid_ctwa'):
    """PUB128 — PROPOSE les structures d'un micro-test terrain.

    Circuit propose→approve NORMAL : deux ``EngineAction`` PROPOSÉES (une
    campagne + un ad set) — l'approbation humaine reste requise et la création
    naît PAUSED (le client force PAUSED, règle #3). Le budget quotidien de l'ad
    set est PLAFONNÉ à ``MICRO_TEST_MAX_DAILY_BUDGET_MAD`` (lu ici, jamais un
    littéral) : un micro-test ne peut pas déraper en dépense.

    L'objectif de campagne est lu dans le catalogue de gabarits de lancement
    (``launch_templates.LAUNCH_TEMPLATES``) — aucun objectif inventé. Lève
    ``ValueError`` (FR) sur un ``ft`` inconnu ou un gabarit inconnu.
    Renvoie ``[EngineAction, EngineAction]``."""
    from . import launch_templates, services
    from .models import EngineAction

    key = str(ft or '').strip().upper()
    if key not in FIELD_TESTS:
        raise ValueError(
            f"Micro-test inconnu « {ft} » : attendu l'un de "
            f"{', '.join(FIELD_TESTS)}.")
    template = launch_templates.LAUNCH_TEMPLATES.get(template_key)
    if template is None:
        raise ValueError(
            f"Gabarit de lancement inconnu « {template_key} » : impossible de "
            f"proposer un micro-test sans objectif de campagne connu.")

    cap = micro_test_budget_cap_mad()
    label = (PROTOCOLS.get(key) or {}).get('label_fr', key)
    campaign_name = f'TEST-TERRAIN {key} {label}'.strip()
    adset_name = f'TEST-TERRAIN {key} ad set'

    campaign_mirror = _field_test_campaign(company, campaign_name)
    if campaign_mirror is None:
        # La campagne n'existe pas encore : on ne propose QUE la campagne. Un ad
        # set sans ``campaign_id`` réel serait un payload CREUX que le vrai Graph
        # rejetterait même après approbation (classe de défaut PUB119).
        existing = _open_field_test_action(
            company, key, EngineAction.Kind.CREATE_CAMPAIGN)
        if existing is not None:
            return [existing]
        return [services.propose_action(
            company, kind=EngineAction.Kind.CREATE_CAMPAIGN,
            reason_fr=(
                f"Micro-test terrain {key} ({label}) : campagne de test "
                f"proposée — née PAUSED à l'application. Son ad set (budget "
                f"plafonné à {cap} MAD/jour) sera proposé dès que la campagne "
                f"existera."),
            payload={'name': campaign_name, 'objective': template['objective'],
                     'field_test': key, 'city': str(city or '').strip()},
            proposed_by=proposed_by)]

    existing = _open_field_test_action(
        company, key, EngineAction.Kind.CREATE_ADSET)
    if existing is not None:
        return [existing]
    return [services.propose_action(
        company, kind=EngineAction.Kind.CREATE_ADSET,
        reason_fr=(
            f"Micro-test terrain {key} : ad set de test proposé sur la campagne "
            f"« {campaign_name} », budget quotidien plafonné à {cap} MAD "
            f"(plafond dur des micro-tests) — né PAUSED à l'application."),
        payload={
            'name': adset_name,
            'campaign_id': campaign_mirror.meta_id,
            'field_test': key,
            'extra_fields': {
                'daily_budget': int(cap * services.CENTIMES_PER_MAD)},
        },
        proposed_by=proposed_by)]


def _field_test_campaign(company, campaign_name):
    """Miroir de la campagne de micro-test déjà créée (``None`` sinon) — jamais un
    ``campaign_id`` fabriqué."""
    from .models import AdCampaignMirror
    return (AdCampaignMirror.objects
            .filter(company=company, name=campaign_name)
            .exclude(meta_id='').first())


def _open_field_test_action(company, ft, kind):
    """Proposition de micro-test DÉJÀ ouverte pour ce (test, kind) — re-cliquer
    ne double jamais une proposition."""
    from .models import EngineAction
    return (EngineAction.objects
            .filter(company=company, kind=kind,
                    status=EngineAction.Statut.PROPOSEE,
                    payload__field_test=ft)
            .order_by('-id').first())
