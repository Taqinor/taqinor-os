"""Copilote vague 2 (lane CALA) — les actions de l'assistant sur le calepinage.

Catalogue déclaré en code (registre AG1, :mod:`apps.agent.registry`) et
découvert par le manifeste (``platform.py`` → ``agent_actions_module``,
ARC33) : les actions disparaissent quand le module calepinage est éteint pour
la société. Toutes naissent dans le lot ``copilote`` (servies seulement copilote
allumé) ; hors noyau, elles sont ``natif_seul`` (jamais servies à LangChain).

Ce module ne contient AUCUNE logique d'exécution : chaque action nomme une
route qui re-vérifie permission ET société à l'exécution (``calepinage_voir``
pour lire, ``calepinage_gerer`` pour écrire — les gardes réelles des routes).
``company`` n'apparaît jamais dans les entrées ; aucune entrée ``forcer``,
``derogation_electrique``, ``taux_tva``, ``remise_globale`` ni ``remplacer``.

Règles qui bornent ce que l'assistant DIT (décisions D-ACAL) :
* la production montrée au client est celle du DEVIS (D-ACAL-6) ; le P50 du
  calepinage est une étude technique INTERNE, jamais un texte pour le client ;
* production en « borne haute » (pertes non renseignées) : le dire tel quel,
  ne citer ni P90 ni PR (D-ACAL-7) ;
* un verdict électrique BLOQUANT se lève à l'écran par un approbateur
  (dérogation tracée, D-ACAL-9) — jamais par l'assistant ;
* l'approbation et le pack technique restent humains (D-ACAL-11/24) ;
* l'assistant ne dessine pas : pour dessiner, il donne le lien de l'atelier.
"""
from __future__ import annotations

from apps.agent.registry import (
    AgentAction, LOT_COPILOTE, RISK_INTERNAL, register, _REGISTRY,
)

#: Les deux codes de la garde réelle des routes (``permissions.py``).
VOIR = 'calepinage_voir'
GERER = 'calepinage_gerer'

BASE = '/api/django/calepinage/calepinages/'

#: La règle de lecture de la production, répétée dans chaque description qui
#: la sert (le modèle ne lit que la description de l'outil qu'il appelle).
REGLE_PRODUCTION = (
    "Le P50 est une étude technique INTERNE du calepinage : la production "
    "montrée au client est celle du devis. Si « mention » dit « borne "
    "haute », dis-le tel quel et ne cite ni P90 ni PR.")


def _schema(proprietes, requis=()):
    return {'type': 'object', 'properties': proprietes,
            'required': list(requis), 'additionalProperties': False}


ENTIER = {'type': 'integer', 'minimum': 1}


DU_LEAD = AgentAction(
    key='calepinage.du_lead',
    label="Où en est le calepinage d'un lead",
    description=(
        "Sert à : savoir si un lead a un calepinage, où il en est (conception, "
        "simulation, devis lié, approbation, reprise de la visite) et le geste "
        "suivant (« a_faire »). Ne pas utiliser pour : dessiner (donne le lien "
        "« lien »), ni compter des panneaux avant dessin "
        "(calepinage.contenance). Exemple : « où en est le calepinage de "
        "Karim Alami ? » → lead=1637. Résultat : le résumé du calepinage "
        "ouvert, ou null et a_faire=creer (suite : calepinage.preparer). "
        + REGLE_PRODUCTION),
    endpoint=BASE + 'du-lead/',
    method='GET',
    inputs=_schema({'lead': dict(ENTIER, description='Identifiant du lead.')},
                   ('lead',)),
    required_permission=VOIR,
    risk=RISK_INTERNAL,
    carte='fiche_calepinage',
    lot=LOT_COPILOTE,
)

RESUME = AgentAction(
    key='calepinage.resume',
    label="Résumé d'un calepinage",
    description=(
        "Sert à : expliquer un calepinage connu par son identifiant (ou une "
        "de ses variantes) : modules, kWc, pans, simulation, pertes "
        "principales, verdict électrique, devis lié, approbation. Ne pas "
        "utiliser pour : un lead (calepinage.du_lead). Exemple : « explique-"
        "moi le résultat du calepinage 12 » → id=12. Résultat : un résumé "
        "court avec « a_faire » et « lien ». " + REGLE_PRODUCTION),
    endpoint=BASE + '{id}/resume/',
    method='GET',
    inputs=_schema({'id': dict(ENTIER, description='Identifiant du calepinage.'),
                    'variante': dict(ENTIER, description='Variante du même calepinage (facultatif).')},
                   ('id',)),
    required_permission=VOIR,
    risk=RISK_INTERNAL,
    carte='fiche_calepinage',
    lot=LOT_COPILOTE,
)

VARIANTES_COMPARER = AgentAction(
    key='calepinage.variantes_comparer',
    label='Comparer les variantes',
    description=(
        "Sert à : comparer les variantes d'un calepinage (modules, kWc, "
        "production simulée, écarts à la variante retenue). Ne pas utiliser "
        "pour : retenir une variante (calepinage.retenir). Exemple : « compare "
        "les variantes du calepinage 12 » → id=12. Résultat : une ligne par "
        "variante ; une variante non simulée a ses chiffres à null (jamais "
        "zéro). Ne cite P75/P90 d'une variante que si le résumé dit la "
        "production complète. " + REGLE_PRODUCTION),
    endpoint=BASE + '{id}/comparer/',
    method='GET',
    inputs=_schema({'id': dict(ENTIER, description='Identifiant du calepinage.')},
                   ('id',)),
    required_permission=VOIR,
    risk=RISK_INTERNAL,
    lot=LOT_COPILOTE,
)

SIMULATION_SUIVRE = AgentAction(
    key='calepinage.simulation_suivre',
    label="Suivre une simulation lancée",
    description=(
        "Sert à : relire une simulation lancée par calepinage.simuler, avec "
        "le job_id qu'elle a rendu. Ne pas utiliser pour : lancer une "
        "simulation. Exemple : job_id=88. Résultat : statut du calcul ; "
        "« resultat » null = pas encore fini : relis au tour suivant, jamais "
        "plus de deux relectures dans un tour. En échec, « elements[0].champ » "
        "nomme le réglage à corriger : dis-le, sans recopier "
        "« message_erreur » (texte technique). Une fois fini, enchaîne sur "
        "calepinage.resume."),
    endpoint='/api/django/calepinage/moteur/resultat/{job_id}/',
    method='GET',
    inputs=_schema({'job_id': dict(ENTIER, description='Le job_id rendu par calepinage.simuler.')},
                   ('job_id',)),
    required_permission=VOIR,
    risk=RISK_INTERNAL,
    lot=LOT_COPILOTE,
)

SIMULER = AgentAction(
    key='calepinage.simuler',
    label='Lancer la simulation de production',
    description=(
        "Sert à : lancer (ou relire si rien n'a changé) la simulation de "
        "production d'un calepinage dessiné, ou d'une de ses variantes. "
        "N'écrit que l'étude technique interne : aucun statut, aucun devis. "
        "Ne pas utiliser pour : un calepinage sans pans équipés (dessiner "
        "d'abord, lien de l'atelier). Exemple : « lance la simulation du "
        "calepinage 12 » → id=12. Résultat : 202 avec un job_id (suis-le avec "
        "calepinage.simulation_suivre), ou 200 deja_calcule (enchaîne sur "
        "calepinage.resume). Un refus 409 NOMME le réglage manquant : "
        "« parametres.simulation.* » = réglage société (Paramètres du "
        "calepinage), « plans » = panneau non désigné (onglet Matériel "
        "électrique), « site.pin » = épingle du site dans l'atelier, "
        "« temperatures » = saisies électriques ; dis-le et donne le lien du "
        "calepinage (erp.ouvrir). Ne relance jamais pour forcer un calcul."),
    endpoint=BASE + '{id}/simuler/',
    method='POST',
    inputs=_schema({'id': dict(ENTIER, description='Identifiant du calepinage.'),
                    'variante_id': dict(ENTIER, description='Variante du même calepinage (facultatif).')},
                   ('id',)),
    required_permission=GERER,
    risk=RISK_INTERNAL,
    lot=LOT_COPILOTE,
    objets={'id': 'calepinage', 'variante_id': 'variante'},
)

ACTIONS = (DU_LEAD, RESUME, VARIANTES_COMPARER, SIMULATION_SUIVRE, SIMULER)


def register_actions() -> None:
    """Enregistre les actions ``calepinage.*`` (idempotent : une clé déjà
    posée est ignorée) — appelée par la découverte des manifestes (ARC33)."""
    for action in ACTIONS:
        if action.key not in _REGISTRY:
            register(action)
