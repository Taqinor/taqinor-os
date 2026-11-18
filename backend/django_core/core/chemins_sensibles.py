"""Masquage des secrets portés DANS une adresse, pour toute sortie d'observabilité.

Couche de FONDATION : n'importe aucune app métier (contrat import-linter
``core-foundation-is-a-base-layer``). Une app dont une route porte un secret
dans son chemin (ex. le calendrier abonné de ``taches`` :
``…/taches/flux/<jeton>.ics``, adresse imposée par l'iPhone) DÉCLARE ses motifs
en ``ready()`` ; ``core`` ne connaît que le NOM, le MOTIF et le REMPLACEMENT :

    chemins_sensibles.enregistrer('taches.flux', r'(/taches/flux/)[^/?#.]+', r'\\1<masqué>')

``masquer(texte)`` applique tous les motifs déclarés, dans l'ordre de leur
déclaration ; c'est l'UNIQUE fonction de masquage, appelée par chaque point de
sortie :

* ``core.observability`` : le contexte de requête (``path``, ``request_id``) —
  donc le champ ``path`` du journal JSON, le journal d'accès ``core.request``,
  la trace ``core.slow_request`` et l'étiquette Sentry ``route`` ;
* chaque enregistrement de journal (fabrique posée par la première
  déclaration) : message, arguments chaînes, pile d'exception ; le formateur
  JSON (``core.logging_ext``) masque aussi le message et la pile qu'il écrit ;
* Sentry (``masquer_evenement``, branché en ``before_send`` ET
  ``before_send_transaction``) : adresse, en-têtes (``Referer``), messages,
  piles et variables locales, fil d'Ariane, étiquettes, nom de transaction.

Sans aucune déclaration : no-op total (aucune fabrique posée, ``masquer`` rend
sa valeur telle quelle).
"""
from __future__ import annotations

import copy
import logging
import re

# Registre en mémoire : { nom: (motif compilé, remplacement) } (ordre de déclaration).
_MOTIFS: dict = {}
_FABRIQUE_POSEE = False
# Garde-fou de la descente dans un évènement Sentry (aucune boucle possible).
_PROFONDEUR_MAX = 64


def enregistrer(nom, motif, remplacement):
    """Déclare (ou remplace, idempotent) un motif de secret dans une adresse."""
    if not nom or not motif:
        raise ValueError('Chemin sensible : nom et motif requis.')
    _MOTIFS[nom] = (re.compile(motif), remplacement)
    _poser_fabrique()


def retirer(nom):
    """Retire une déclaration (surtout utile en test pour isoler le registre)."""
    _MOTIFS.pop(nom, None)


def masquer(valeur):
    """``valeur`` dont chaque secret déclaré est remplacé ; une non-chaîne est rendue telle quelle."""
    if not isinstance(valeur, str) or not _MOTIFS:
        return valeur
    for motif, remplacement in tuple(_MOTIFS.values()):
        valeur = motif.sub(remplacement, valeur)
    return valeur


def masquer_evenement(event, hint=None):
    """Un évènement Sentry (erreur, message ou transaction) dont toute chaîne est masquée."""
    if not _MOTIFS:
        return event
    return _masquer_profond(event, 0)


def _masquer_profond(valeur, profondeur):
    if isinstance(valeur, str):
        return masquer(valeur)
    if profondeur > _PROFONDEUR_MAX:
        return valeur
    if isinstance(valeur, dict):
        return {masquer(cle): _masquer_profond(element, profondeur + 1) for cle, element in valeur.items()}
    if isinstance(valeur, list) or type(valeur) is tuple:
        return type(valeur)(_masquer_profond(element, profondeur + 1) for element in valeur)
    return valeur


def masquer_enregistrement(record):
    """Masque un enregistrement de journal en place : message, arguments chaînes, pile d'exception.

    Rien n'est formaté d'avance quand aucun secret n'y figure : un message sans secret garde son
    gabarit et ses arguments (le regroupement des journaux et de Sentry est inchangé)."""
    if not _MOTIFS:
        return
    if isinstance(record.msg, str):
        record.msg = masquer(record.msg)
    if isinstance(record.args, dict):
        # Jamais un `dict` nu à la place de l'objet de l'appelant : un dictionnaire spécialisé (le journal
        # d'accès de gunicorn rend « - » pour un en-tête absent) garde son type ; rien n'est réécrit quand
        # rien n'est masqué, et l'objet de l'appelant n'est jamais modifié (copie).
        masquees = {cle: masquee for cle, valeur in record.args.items()
                    if (masquee := masquer(valeur)) != valeur}
        if masquees:
            copie = copy.copy(record.args)
            copie.update(masquees)
            record.args = copie
    elif isinstance(record.args, tuple):
        masques = tuple(masquer(valeur) for valeur in record.args)
        if masques != record.args:
            record.args = masques
    if record.exc_info and record.exc_info[0] is not None and not record.exc_text:
        pile = logging.Formatter().formatException(record.exc_info)
        masquee = masquer(pile)
        if masquee != pile:
            record.exc_text = masquee


def _poser_fabrique():
    """Pose (une fois par process) la fabrique d'enregistrements qui masque chaque journal émis,
    quelle que soit la configuration ``LOGGING`` (JSON, production, développement, Celery)."""
    global _FABRIQUE_POSEE
    if _FABRIQUE_POSEE:
        return
    origine = logging.getLogRecordFactory()

    def fabrique(*args, **kwargs):
        record = origine(*args, **kwargs)
        masquer_enregistrement(record)
        return record

    logging.setLogRecordFactory(fabrique)
    _FABRIQUE_POSEE = True
