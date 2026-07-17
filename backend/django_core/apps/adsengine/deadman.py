"""ADSENG19 — [GATED: décision fondateur] Règle Meta native « homme-mort ».

CE MODULE N'ACTIVE RIEN. C'est une SPEC exécutable + un générateur de COMMANDE
d'installation documentée — jamais un appel réseau, jamais une activation. La
décision de l'installer (et le fait de lancer la commande à la main sur le
compte publicitaire) appartient au fondateur, PAS à ce code.

Ce que la règle apporterait
---------------------------
Une règle « homme-mort » (dead-man switch) est une règle Meta NATIVE, hébergée
par Meta via l'API ``adrules_library`` — donc INDÉPENDANTE de notre
infrastructure (elle continue de protéger même si notre Celery, notre serveur ou
notre réseau tombent). Elle met en PAUSE tout ce qui dépasse un plafond de
dépense CATASTROPHE (pas le pacing quotidien — un garde-fou de dernier recours,
bien au-dessus des plafonds ENG20/ENG21). C'est la seule protection qui survit à
une panne totale de notre côté.

Pourquoi une commande manuelle et pas du code qui l'installe
------------------------------------------------------------
VÉRIFIÉ : le CLI Meta Ads n'expose PAS ``adrules_library`` — seule l'API Graph
brute le fait. Et surtout : installer programmatiquement une règle qui agit sur
le compte serait exactement le pouvoir que la règle #3 (« les campagnes naissent
en pause, jamais d'activation programmatique ») nous interdit d'exercer sans
décision explicite. Donc ce module se contente de CONSTRUIRE le payload et de
RENDRE la commande ``curl`` que le fondateur exécutera lui-même, une fois, à la
main. ``DEADMAN_ENABLED`` reste ``False`` en dur : rien ici ne touche Meta.

Le déclencheur de décision
--------------------------
Installer la règle est pertinent dès qu'un budget réel tourne en autonomie (mode
autonome ENG38 activable) ET qu'un plafond catastrophe chiffré est arrêté par le
fondateur. Tant que le moteur est OFF par défaut, la règle est superflue.
"""
from __future__ import annotations

# ── Invariant structurel : ce module n'active RIEN ────────────────────────────
# OFF EN DUR. Aucune bascule d'exécution n'existe dans le code : l'installation
# est un geste MANUEL du fondateur (la commande rendue ci-dessous), jamais un
# effet de ce module. Ne jamais mettre ``True`` ici « pour tester » — il n'y a
# aucun chemin qui appelle Meta de toute façon.
DEADMAN_ENABLED = False

# Plafond CATASTROPHE par défaut (MAD/jour, dépense compte). Volontairement TRÈS
# au-dessus des plafonds de pacing (ENG20 ~enveloppe mensuelle / ENG21 ~budgets
# ad set) : c'est un dernier recours, pas un régulateur. Le fondateur fixe la
# valeur réelle au moment de la décision — cette constante n'est qu'un défaut sûr.
DEFAULT_CATASTROPHE_CEILING_MAD = 2000

# Endpoint Graph brut de la bibliothèque de règles (le CLI ne l'expose pas).
GRAPH_API_VERSION = 'v19.0'
ADRULES_EDGE = 'adrules_library'


def build_deadman_rule_spec(*, ceiling_mad=DEFAULT_CATASTROPHE_CEILING_MAD,
                            name='Homme-mort (plafond catastrophe)'):
    """Construit le PAYLOAD de la règle ``adrules_library`` — DONNÉES PURES.

    La règle : si la dépense du compte sur la fenêtre du jour dépasse
    ``ceiling_mad``, METTRE EN PAUSE toutes les campagnes du compte. Évaluée au
    rythme le plus serré que Meta autorise (semi-horaire) pour que le plafond
    catastrophe ne soit jamais franchi longtemps.

    Aucun effet de bord : renvoie un dict. Le fondateur (ou la commande rendue
    par :func:`deadman_install_command`) l'envoie à Meta — jamais ce code.
    """
    return {
        'name': name,
        # ÉVALUATION : dépense du compte au-delà du plafond catastrophe.
        'evaluation_spec': {
            'evaluation_type': 'SCHEDULE',
            'filters': [
                {'field': 'entity_type', 'value': 'CAMPAIGN',
                 'operator': 'EQUAL'},
                {'field': 'time_preset', 'value': 'TODAY',
                 'operator': 'EQUAL'},
                {'field': 'spent', 'value': int(ceiling_mad) * 100,
                 'operator': 'GREATER_THAN'},  # Meta compte en centimes
            ],
        },
        # EXÉCUTION : PAUSE (jamais ACTIVATE) — cohérent règle #3.
        'execution_spec': {
            'execution_type': 'PAUSE',
            'execution_options': [
                {'field': 'user_ids', 'value': [], 'operator': 'EQUAL'},
                {'field': 'alert_preferences',
                 'value': {'instapush': 'true', 'email': 'true'},
                 'operator': 'EQUAL'},
            ],
        },
        # Le rythme d'évaluation le plus serré côté Meta.
        'schedule_spec': {'schedule_type': 'SEMI_HOURLY'},
        # La règle NAÎT active côté Meta (c'est un garde-fou) — mais c'est le
        # fondateur qui la crée à la main. Ce champ décrit le payload voulu ; il
        # n'active rien dans NOTRE système (nous ne créons jamais cette règle).
        'status': 'ENABLED',
    }


def deadman_install_command(*, ad_account_id,
                            ceiling_mad=DEFAULT_CATASTROPHE_CEILING_MAD,
                            access_token_env='META_SYSTEM_USER_TOKEN'):
    """Rend la COMMANDE ``curl`` d'installation — une CHAÎNE à exécuter À LA MAIN.

    Le jeton n'est JAMAIS incorporé : la commande lit une variable
    d'environnement (``$META_SYSTEM_USER_TOKEN`` par défaut), donc aucun secret
    ne transite par ce code ni par les journaux. Cette fonction NE LANCE RIEN —
    elle documente ce que le fondateur tapera, une fois, s'il décide d'installer
    la règle.
    """
    import json

    spec = build_deadman_rule_spec(ceiling_mad=ceiling_mad)
    url = (f'https://graph.facebook.com/{GRAPH_API_VERSION}/'
           f'{ad_account_id}/{ADRULES_EDGE}')
    fields = {
        'name': spec['name'],
        'evaluation_spec': json.dumps(spec['evaluation_spec']),
        'execution_spec': json.dumps(spec['execution_spec']),
        'schedule_spec': json.dumps(spec['schedule_spec']),
        'status': spec['status'],
    }
    data_args = ' \\\n  '.join(
        f"--data-urlencode {json.dumps(f'{k}={v}')}" for k, v in fields.items())
    return (
        f'# ADSENG19 — installation MANUELLE de la règle homme-mort (fondateur).\n'
        f'# Le CLI Meta n\'expose pas adrules_library ; c\'est l\'API Graph brute.\n'
        f'# Prérequis : export ${access_token_env}=<jeton System User>.\n'
        f'curl -X POST "{url}" \\\n'
        f'  {data_args} \\\n'
        f'  --data-urlencode "access_token=${access_token_env}"'
    )


def deadman_status():
    """État affichable : la règle homme-mort est OFF par design (rien d'activé).

    Sert de sonde honnête pour la console/les docs : elle confirme qu'AUCUNE
    règle n'est posée par notre système et que l'installation reste un geste
    manuel gated fondateur.
    """
    return {
        'enabled': DEADMAN_ENABLED,          # toujours False (OFF en dur)
        'installed_by_us': False,            # nous ne créons jamais la règle
        'default_ceiling_mad': DEFAULT_CATASTROPHE_CEILING_MAD,
        'requires': 'décision fondateur + exécution manuelle de la commande',
    }
