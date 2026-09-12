"""NTAPI12 — abonnements webhook par FILTRE FIN (évènement + condition).

Aujourd'hui un abonnement est binaire : « je veux tous les `facture.paid` ».
Un intégrateur qui ne s'intéresse qu'aux grosses factures reçoit donc tout et
filtre chez lui — et paie la bande passante, la latence et le bruit. NTAPI12
ajoute une condition PAR ÉVÈNEMENT, évaluée côté serveur AVANT livraison.

Forme stockée dans ``Webhook.filtres`` (dict, ``{}`` = aucun filtre) ::

    {"facture.paid": {"montant_ttc__gte": 10000},
     "lead.created": {"canal": "site_web"}}

Chaque valeur est soit un **dict de lookups** façon Django (``champ__op``, ou
``champ`` seul pour l'égalité), soit — pour les cas complexes — un **arbre de
conditions `core.rules`** complet (``{"op": "or", "conditions": [...]}``). Les
deux sont évalués par le MÊME moteur : ``core.rules.evaluate_condition_group``
(FG367, déjà en place) — aucune logique de comparaison n'est ré-écrite ici, on
ne fait que TRADUIRE la forme courte en arbre.

TROIS PROPRIÉTÉS QUI COMPTENT

* **Opt-in, évènement par évènement.** Un évènement absent du dict n'est jamais
  filtré : un webhook sans ``filtres`` se comporte EXACTEMENT comme avant.
* **Un filtre illisible ne fait jamais taire un webhook.** Une condition
  malformée (JSON inattendu, opérateur inconnu) est IGNORÉE et la livraison a
  lieu — le contraire transformerait une faute de frappe dans un écran de
  réglages en panne silencieuse d'intégration, le pire mode d'échec possible
  pour ce genre de fonctionnalité.
* **Champ absent = condition fausse.** C'est le comportement de `core.rules`
  (une feuille sur un champ manquant vaut ``False``), et c'est le bon : filtrer
  sur un champ que le payload ne porte pas ne doit pas laisser tout passer.

Le filtre s'applique à l'émission AUTOMATIQUE (``delivery.dispatch_event``). Un
replay/test-ping MANUEL (FG102) reste délibérément non filtré : c'est un geste
d'administrateur qui veut voir partir CET évènement précis.
"""
from __future__ import annotations

import logging

from core.rules import LEAF_OPERATORS, evaluate_condition_group

logger = logging.getLogger(__name__)

# Suffixe de lookup → opérateur de feuille `core.rules`. Sans suffixe reconnu,
# la clé entière est un nom de champ et l'opérateur est l'égalité.
_SUFFIXES = {
    'eq': 'eq',
    'ne': 'ne',
    'gt': 'gt',
    'gte': 'gte',
    'lt': 'lt',
    'lte': 'lte',
    'in': 'in',
    'not_in': 'not_in',
    'contains': 'contains',
    'startswith': 'startswith',
    'exists': 'exists',
}


def _est_arbre(valeur) -> bool:
    """Un arbre `core.rules` porte un ``op`` logique ou une clé ``conditions``."""
    if not isinstance(valeur, dict):
        return False
    op = valeur.get('op')
    if isinstance(op, str) and op.lower() in ('and', 'or', 'not'):
        return True
    return 'conditions' in valeur


def lookup_vers_feuille(cle, valeur):
    """``('montant_ttc__gte', 10000)`` → feuille `core.rules`.

    Une clé sans suffixe reconnu (``'canal'``) devient une égalité. Un suffixe
    inconnu (``'montant__zzz'``) n'est PAS deviné : la clé entière est alors
    traitée comme un nom de champ — la condition sera simplement fausse, jamais
    une comparaison inventée."""
    champ, sep, suffixe = str(cle).rpartition('__')
    if sep and suffixe in _SUFFIXES and champ:
        return {'field': champ, 'operator': _SUFFIXES[suffixe],
                'value': valeur}
    return {'field': str(cle), 'operator': 'eq', 'value': valeur}


def condition_vers_arbre(condition):
    """Normalise une condition stockée en arbre `core.rules`, ou ``None``.

    ``None`` signifie « pas de condition exploitable » → aucun filtrage (la
    livraison a lieu), jamais « bloque tout »."""
    if condition in (None, {}, []):
        return None
    if _est_arbre(condition):
        return condition
    if isinstance(condition, dict):
        feuilles = [lookup_vers_feuille(k, v) for k, v in condition.items()]
        if not feuilles:
            return None
        # Plusieurs lookups dans le même dict = ET (même sémantique qu'un
        # `filter(**kwargs)` Django, pour ne surprendre personne).
        return {'op': 'and', 'conditions': feuilles}
    return None


def payload_passe(condition, payload) -> bool:
    """``True`` si ``payload`` satisfait ``condition`` (ou s'il n'y a pas de
    condition exploitable). Ne lève jamais."""
    arbre = condition_vers_arbre(condition)
    if arbre is None:
        return True
    if not isinstance(payload, dict):
        return True
    try:
        return bool(evaluate_condition_group(arbre, payload))
    except Exception:  # noqa: BLE001 — un filtre cassé ne fait jamais taire
        logger.exception('Filtre webhook illisible — livraison maintenue')
        return True


def webhook_accepte(webhook, event, payload) -> bool:
    """``True`` si CE webhook doit recevoir CET évènement.

    Suppose l'abonnement déjà vérifié par l'appelant (``subscribes_to``) : ici
    on ne tranche QUE la condition fine."""
    filtres = getattr(webhook, 'filtres', None) or {}
    if not isinstance(filtres, dict):
        return True
    return payload_passe(filtres.get(event), payload)


def erreurs_de_filtres(filtres):
    """Valide une valeur de ``Webhook.filtres`` (écran Paramètres / API).

    Renvoie une liste de messages FR (vide = valide). La validation se fait à
    l'ENREGISTREMENT — c'est là qu'une faute de frappe doit être signalée, pas
    six semaines plus tard sous la forme d'une intégration muette."""
    from core.rules import validate_condition_group

    from .constants import ALL_EVENTS

    erreurs = []
    if filtres in (None, ''):
        return erreurs
    if not isinstance(filtres, dict):
        return ["« filtres » doit être un objet JSON "
                "(évènement → condition)."]
    for event, condition in filtres.items():
        if event not in ALL_EVENTS:
            erreurs.append(f'Évènement inconnu dans « filtres » : {event}.')
            continue
        if _est_arbre(condition):
            erreurs.extend(
                f'{event} : {msg}'
                for msg in validate_condition_group(condition))
            continue
        if not isinstance(condition, dict):
            erreurs.append(
                f'{event} : la condition doit être un objet '
                f'(ex. {{"montant_ttc__gte": 10000}}).')
            continue
        for cle in condition:
            feuille = lookup_vers_feuille(cle, None)
            if feuille['operator'] not in LEAF_OPERATORS:
                erreurs.append(f'{event} : opérateur inconnu pour « {cle} ».')
    return erreurs
