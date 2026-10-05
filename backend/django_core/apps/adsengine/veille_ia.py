"""VEIL22 — Tri IA DANS l'ERP, ÉTEINT sans clé (pour la mise en service).

D-VEIL-8. Appel de l'API Anthropic (Messages) par ``httpx`` — aucun nouveau
paquet. Clé ``VEILLE_IA_CLE_API`` (SÉPARÉE de la clé du service FastAPI),
modèles ``VEILLE_IA_MODELE_TRI`` / ``VEILLE_IA_MODELE_AMBIGU`` en réglages
(jamais en dur). Même consigne que le tri hors ligne VEIL21
(``data/veille_consigne/v1.md``). Seuls les champs de la fiche VEIL21
(``veille_decouverte.CHAMPS_FICHE``) sont envoyés.

Sortie attendue ``{classe, confiance, dropshipper, indices}``. Une réponse
invalide, un refus ou un délai dépassé donnent ``incertain`` (jamais une
classe devinée). Le motif enregistré ne cite QUE des champs présents dans la
fiche ; un indice dont la valeur n'est pas dans la fiche est écarté. Les
jetons (``usage``) sont enregistrés sur le verdict. Une décision humaine n'est
jamais écrasée.

DÉPENDANCE PAYANTE : API Anthropic, inactive tant que la clé est vide.
"""
from __future__ import annotations

import json
import logging

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

URL_MESSAGES = 'https://api.anthropic.com/v1/messages'
VERSION_API = '2023-06-01'
MAX_TOKENS = 1024
MESSAGE_NON_CONFIGURE = ('Tri IA non configuré : aucune clé API ou aucun '
                         'modèle de tri n\'est réglé.')


def _reglage(nom, defaut=''):
    return getattr(settings, nom, defaut) or defaut


def configuration():
    return {
        'cle': str(_reglage('VEILLE_IA_CLE_API')),
        'modele_tri': str(_reglage('VEILLE_IA_MODELE_TRI')),
        'modele_ambigu': str(_reglage('VEILLE_IA_MODELE_AMBIGU')),
        'seuil': float(_reglage('VEILLE_IA_SEUIL_AMBIGU', 0.7)),
        'delai': float(_reglage('VEILLE_IA_DELAI_S', 60)),
    }


def est_configure():
    config = configuration()
    return bool(config['cle'] and config['modele_tri'])


def _extraire_objet(texte):
    texte = (texte or '').strip()
    debut, fin = texte.find('{'), texte.rfind('}')
    if debut < 0 or fin < debut:
        raise ValueError('aucun objet JSON')
    objet = json.loads(texte[debut:fin + 1])
    if isinstance(objet, list):
        objet = objet[0] if objet else {}
    if not isinstance(objet, dict):
        raise ValueError('objet JSON attendu')
    return objet


def appeler(fiche, modele, *, http_client=None, config=None):
    """UN appel Messages. Renvoie ``(objet | None, jetons_entree,
    jetons_sortie, raison)`` ; ``objet`` vaut ``None`` si la réponse est
    invalide, refusée ou hors délai (``raison`` en FR)."""
    from .veille_decouverte import CHAMPS_FICHE, lire_consigne

    config = config or configuration()
    corps = {
        'model': modele,
        'max_tokens': MAX_TOKENS,
        'system': lire_consigne(),
        'messages': [{
            'role': 'user',
            'content': json.dumps({c: fiche.get(c) for c in CHAMPS_FICHE},
                                  ensure_ascii=False),
        }],
    }
    entetes = {'x-api-key': config['cle'],
               'anthropic-version': VERSION_API,
               'content-type': 'application/json'}
    try:
        if http_client is not None:
            reponse = http_client.post(URL_MESSAGES, json=corps,
                                       headers=entetes,
                                       timeout=config['delai'])
        else:
            with httpx.Client(timeout=config['delai']) as client:
                reponse = client.post(URL_MESSAGES, json=corps,
                                      headers=entetes)
    except httpx.TimeoutException:
        return None, None, None, 'délai dépassé'
    except httpx.HTTPError as exc:
        return None, None, None, f'erreur réseau ({type(exc).__name__})'
    try:
        donnees = reponse.json()
    except ValueError:
        donnees = {}
    usage = donnees.get('usage') or {}
    entree = usage.get('input_tokens')
    sortie = usage.get('output_tokens')
    if reponse.status_code >= 400:
        return None, entree, sortie, f'HTTP {reponse.status_code}'
    if donnees.get('stop_reason') == 'refusal':
        return None, entree, sortie, 'refus du modèle'
    texte = ''.join(b.get('text', '') for b in donnees.get('content') or []
                    if isinstance(b, dict) and b.get('type') == 'text')
    try:
        return _extraire_objet(texte), entree, sortie, ''
    except (ValueError, TypeError):
        return None, entree, sortie, 'réponse invalide'


def _texte_fiche(fiche):
    return json.dumps(fiche, ensure_ascii=False).lower()


def indices_valides(fiche, indices):
    """Indices dont le champ est un champ de la fiche ET la valeur y figure."""
    from .veille_decouverte import CHAMPS_FICHE

    texte = _texte_fiche(fiche)
    sortie = []
    for indice in indices or []:
        if not isinstance(indice, dict):
            continue
        champ = str(indice.get('champ') or '')
        valeur = str(indice.get('valeur') or '').strip()
        if champ in CHAMPS_FICHE and valeur and valeur.lower() in texte:
            sortie.append({'champ': champ, 'valeur': valeur[:200]})
    return sortie


def _ligne(fiche, objet, modele, entree, sortie, raison=''):
    """Ligne de verdict au format VEIL21 (``importer_verdict_ia``)."""
    from .veille_decouverte import _classes

    classes = _classes()
    objet = objet or {}
    classe = objet.get('classe') if objet.get('classe') in classes \
        else 'incertain'
    dropshipper = objet.get('dropshipper') \
        if objet.get('dropshipper') in ('oui', 'non', 'incertain') \
        else 'incertain'
    try:
        confiance = max(0.0, min(1.0, float(objet.get('confiance'))))
    except (TypeError, ValueError):
        confiance = 0.0
    if raison:
        classe, dropshipper, confiance = 'incertain', 'incertain', 0.0
    indices = [] if raison else indices_valides(fiche, objet.get('indices'))
    if raison:
        motif = f'Tri IA sans réponse exploitable ({raison}) : incertain.'
    else:
        motif = (f'Tri IA : {classes[classe].lower()} '
                 f'(confiance {confiance:.2f}).')
        if indices:
            motif += ' Champs cités : ' + ', '.join(
                sorted({i['champ'] for i in indices})) + '.'
    return {'page_id': fiche['page_id'], 'classe': classe,
            'confiance': confiance, 'dropshipper': dropshipper,
            'indices': indices, 'modele': modele, 'motif_fr': motif,
            'jetons_entree': entree, 'jetons_sortie': sortie}


def trier_annonceur(annonceur, *, http_client=None):
    """Trie UN annonceur. Sans clé : AUCUN appel, ``{'statut':
    'non_configure', 'message_fr': ...}``. Sinon ``{'statut', 'ligne'}``
    après enregistrement (``importe`` | ``ignore`` si décision humaine)."""
    from .veille_decouverte import fiche_tri, importer_verdict_ia

    config = configuration()
    if not (config['cle'] and config['modele_tri']):
        return {'statut': 'non_configure', 'message_fr': MESSAGE_NON_CONFIGURE}
    fiche = fiche_tri(annonceur)
    objet, entree, sortie, raison = appeler(
        fiche, config['modele_tri'], http_client=http_client, config=config)
    ligne = _ligne(fiche, objet, config['modele_tri'], entree, sortie, raison)
    if (not raison and config['modele_ambigu']
            and (ligne['confiance'] < config['seuil']
                 or ligne['dropshipper'] == 'oui')):
        objet2, entree2, sortie2, raison2 = appeler(
            fiche, config['modele_ambigu'], http_client=http_client,
            config=config)
        second = _ligne(fiche, objet2, config['modele_ambigu'], entree2,
                        sortie2, raison2)
        for cle, a, b in (('jetons_entree', entree, entree2),
                          ('jetons_sortie', sortie, sortie2)):
            second[cle] = None if a is None and b is None \
                else (a or 0) + (b or 0)
        ligne = second
    statut, message = importer_verdict_ia(annonceur.company, ligne)
    if statut == 'erreur':
        logger.warning('veille_ia: verdict non enregistré (%s)', message)
    return {'statut': statut, 'message_fr': message, 'ligne': ligne}


def trier_decouverte(decouverte, *, http_client=None):
    """Trie les annonceurs ``incertain`` d'une découverte (aucun appel sans
    clé). Renvoie ``{statut: nombre}``."""
    from .veille_decouverte import annonceurs_de

    if not est_configure():
        return {'non_configure': 0, 'message_fr': MESSAGE_NON_CONFIGURE}
    compte = {}
    for annonceur in annonceurs_de(decouverte).filter(
            classe='incertain').order_by('id'):
        resultat = trier_annonceur(annonceur, http_client=http_client)
        compte[resultat['statut']] = compte.get(resultat['statut'], 0) + 1
    return compte
