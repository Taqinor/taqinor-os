"""ADSENG24 — 3 gabarits de lancement comme DONNÉES (dd-treasury §c).

Chaque gabarit est un dict plat (Résidentiel CTWA / Pompage agricole saisonnier
/ B2B Lead Form) qu'une proposition ``EngineAction`` instancie avec des
surcharges par run (ville, date, variante, budget sous plafond) — plutôt que le
générateur de brief/LLM ne reconstruise une campagne de zéro à chaque fois
(réduit le risque de proposition malformée, dd-treasury §c).

Le registre EST le seed (données, pas des lignes DB — style ``STAGES.py`` /
``rules.RULE_TEMPLATES``) : idempotent par construction, chargé une fois. Les
clés de slots créatifs (``reel``/``static``/``explainer``) sont ALIGNÉES sur
``CreativeAsset.AssetType`` (littéraux partagés, vérifié par test).

RÈGLE #3 (campagnes nées PAUSED) : un lancement à blanc (``dry_run_launch``)
produit une structure dont CHAQUE objet porte ``status='PAUSED'`` — le dry-run
ne touche jamais Meta ; l'application réelle reste la boucle propose→approuve→
applique, où ``meta_client`` force PAUSED de toute façon.
"""
from __future__ import annotations

import copy

# Statut de toute création (invariant #3) — littéral local (pas d'import
# ``meta_client`` : ce module est de la DONNÉE pure, sans dépendance réseau).
PAUSED_STATUS = 'PAUSED'
# Optimisation de budget : ABO par défaut (sous le plancher CBO à 2-4 ad sets,
# dd-treasury §B2 — CBO interdit tant que budget_applier n'y autorise pas).
ABO = 'ABO'
# Placements : Advantage+ (automatiques) recommandés par défaut (dd-treasury
# §c, Meta Business Help Center).
PLACEMENTS_ADVANTAGE_PLUS = 'advantage_plus'

# Slots créatifs — ALIGNÉS sur ``CreativeAsset.AssetType`` (vérifié par test).
SLOT_REEL = 'reel'
SLOT_STATIC = 'static'
SLOT_EXPLAINER = 'explainer'


LAUNCH_TEMPLATES = {
    'resid_ctwa': {
        'key': 'resid_ctwa',
        'label': 'Résidentiel CTWA',
        'market': 'resid',
        'objective': 'ctwa',  # Click-to-WhatsApp (OUTCOME_ENGAGEMENT)
        'budget_optimization': ABO,
        'num_adsets': (2, 3),  # broad + city-narrowed
        # Sous le plafond quotidien défaut (100 MAD) : 40/40/20.
        'default_budget_split_mad': [40, 40, 20],
        'placements': PLACEMENTS_ADVANTAGE_PLUS,
        # no-fake-footage : enhancements créatifs OFF par défaut.
        'creative_enhancements': False,
        'seasonal': False,
        'qualifying_questions': [
            "Bonjour, je suis intéressé par un projet solaire résidentiel à "
            "{ville}. Quelle est votre facture mensuelle d'électricité ?",
        ],
        'creative_slots': {SLOT_REEL: 1, SLOT_STATIC: 1, SLOT_EXPLAINER: 1},
    },
    'agri_pompage': {
        'key': 'agri_pompage',
        'label': 'Pompage agricole (saisonnier)',
        'market': 'agri',
        'objective': 'ctwa',
        'budget_optimization': ABO,
        'num_adsets': (1, 2),  # par région agricole
        'default_budget_split_mad': [60, 40],
        'placements': PLACEMENTS_ADVANTAGE_PLUS,
        'creative_enhancements': False,
        # Flight FRONT-LOADED : le pacing doit savoir que c'est saisonnier pour
        # ne pas flaguer le front-loading comme over_pacing (dd-treasury §c).
        'seasonal': True,
        'qualifying_questions': [
            "Quelle est votre HMT (hauteur manométrique totale) et le débit "
            "souhaité (m³/h) ?",
        ],
        # Pas de reel ; PAS d'onduleur ni de batterie montrés (règle pompage).
        'creative_slots': {SLOT_STATIC: 1, SLOT_EXPLAINER: 1},
    },
    'b2b_leadform': {
        'key': 'b2b_leadform',
        'label': 'B2B Lead Form (Industriel/Commercial)',
        'market': 'indcom',
        'objective': 'leadform',  # native Meta Lead Ads (OUTCOME_LEADS)
        'budget_optimization': ABO,
        'num_adsets': (1, 2),  # zones industrielles / proxy taille société
        'default_budget_split_mad': [50, 30],
        'placements': PLACEMENTS_ADVANTAGE_PLUS,
        'creative_enhancements': False,
        'seasonal': False,
        'qualifying_questions': [
            "Facture mensuelle moyenne (MAD) ?",
            "Type de site (usine / entrepôt / bureaux) ?",
            "Surface de toiture disponible (m²) ?",
        ],
        'creative_slots': {SLOT_EXPLAINER: 1, SLOT_STATIC: 1},
    },
}


def list_templates():
    """Liste ``[{key, label}]`` des gabarits disponibles (le seed)."""
    return [{'key': t['key'], 'label': t['label']}
            for t in LAUNCH_TEMPLATES.values()]


def get_template(key):
    """Copie PROFONDE du gabarit (les appelants surchargent sans muter le
    registre). ``ValueError`` si la clé est inconnue."""
    tpl = LAUNCH_TEMPLATES.get(key)
    if tpl is None:
        raise ValueError(f"Gabarit de lancement inconnu : {key!r}")
    return copy.deepcopy(tpl)


def required_slots(template):
    """Slots créatifs requis d'un gabarit (dict ``type -> min``)."""
    return dict(template.get('creative_slots') or {})


def validate_slots(template, available):
    """Valide les slots créatifs contre la bibliothèque (ENG15/ADSENG27).

    ``available`` : mapping ``asset_type -> nombre disponible`` (assets validés
    policy). Renvoie ``(ok, missing)`` où ``missing`` est ``{type: manquant}``
    (vide si tous les slots sont couverts)."""
    required = required_slots(template)
    missing = {}
    for slot_type, need in required.items():
        have = int((available or {}).get(slot_type, 0))
        if have < need:
            missing[slot_type] = need - have
    return (not missing, missing)


def validate_slots_for_company(company, template_key):
    """Comme ``validate_slots`` mais compte les ``CreativeAsset`` VALIDÉS policy
    de la société PAR type (ENG15) — un asset non validé ne compte jamais."""
    from .models import CreativeAsset
    tpl = get_template(template_key)
    counts = {}
    for asset in CreativeAsset.objects.filter(company=company):
        if asset.is_policy_passed:
            counts[asset.asset_type] = counts.get(asset.asset_type, 0) + 1
    return validate_slots(tpl, counts)


def _resolve_budget_split(template, total_daily_budget_mad):
    """Split budget des ad sets. Sans total → le split par défaut (sous
    plafond). Avec total → réparti proportionnellement au split par défaut."""
    base = list(template.get('default_budget_split_mad') or [])
    if total_daily_budget_mad is None:
        return base
    s = sum(base)
    if s <= 0:
        return base
    return [round(float(total_daily_budget_mad) * b / s, 2) for b in base]


def dry_run_launch(template_key, *, city, launch_date, variant, company=None,
                   total_daily_budget_mad=None):
    """Lancement À BLANC : produit la structure attendue (campagne + ad sets)
    dont CHAQUE objet est ``PAUSED`` (règle #3), nommée via
    ``identity.generate_launch_identity`` — AUCUN appel Meta, aucune écriture.

    Sert à prévisualiser/valider une proposition avant la boucle
    propose→approuve→applique."""
    from . import identity
    tpl = get_template(template_key)
    ident = identity.generate_launch_identity(
        market=tpl['market'], objective=tpl['objective'], city=city,
        launch_date=launch_date, variant=variant, company=company)
    split = _resolve_budget_split(tpl, total_daily_budget_mad)
    campaign_name = ident['campaign_name']
    adsets = []
    for i, budget in enumerate(split, start=1):
        adsets.append({
            'name': ident['adset_name_tmpl'].format(
                campaign_name=campaign_name, n=i),
            'daily_budget_mad': budget,
            'placements': tpl['placements'],
            'status': PAUSED_STATUS,  # règle #3
        })
    return {
        'template': template_key,
        'seasonal': tpl['seasonal'],
        'campaign': {
            'name': campaign_name,
            'objective': tpl['objective'],
            'budget_optimization': tpl['budget_optimization'],
            'placements': tpl['placements'],
            'status': PAUSED_STATUS,  # règle #3 — née PAUSED
        },
        'adsets': adsets,
        'utm': {
            'utm_source': ident['utm_source'],
            'utm_medium': ident['utm_medium'],
            'utm_campaign': ident['utm_campaign'],
        },
        'creative_slots': required_slots(tpl),
        'creative_enhancements': tpl['creative_enhancements'],
        'qualifying_questions': list(tpl['qualifying_questions']),
    }
