"""ACAL400 — le brouillon de l'atelier, AUSSI côté serveur, par utilisateur.

Le brouillon local (``frontend/src/features/calepinage/brouillon.js``) ne vit
que dans UN navigateur ; ce service le range sur le pivot, dans
``Calepinage.brouillons_atelier`` (``{"<id utilisateur>": {layout, horodatage,
base_empreinte}}``), pour qu'un autre poste le propose à la reprise.

* PRIVÉ à l'auteur : la clé est ``user.pk``, jamais lue dans un corps ;
* PÉRIMÉ dès que le document a changé : la lecture compare ``base_empreinte`` à
  l'empreinte « document » ACTUELLE (``layout.empreinte_document``) — rien
  n'est écrit par ``enregistrer_layout`` (fichier mono-écrivain) ;
* SANS EFFET sur le document : écriture par ``update()`` (ni ``save()`` ni
  signaux) — aucune version, ``layout_hash``, empreinte, ``updated_at`` et
  journal inchangés (D-ACAL-4/21).

Contrat : ``contract_samples/calepinage_brouillon.json``.
"""
from __future__ import annotations

from django.db import transaction

from .layout import empreinte_document
from .parametres import _chemin_caractere_interdit

__all__ = ['BrouillonRefuse', 'lire_brouillon', 'enregistrer_brouillon',
           'effacer_brouillon']


class BrouillonRefuse(Exception):
    """Refus nommant son ``champ`` ; ``conflit`` = 409 (sinon 400)."""

    def __init__(self, message, champ, conflit=False):
        super().__init__(message)
        self.champ = champ
        self.conflit = conflit


def _cle(user):
    return str(getattr(user, 'pk', '') or '')


def lire_brouillon(calepinage, user):
    """Le brouillon de ``user`` s'il est encore À JOUR, sinon ``None``."""
    entree = (calepinage.brouillons_atelier or {}).get(_cle(user))
    if not isinstance(entree, dict):
        return None
    if entree.get('base_empreinte') != empreinte_document(
            calepinage.roof_layout):
        return None  # le document a changé depuis : brouillon périmé
    return {cle: entree.get(cle)
            for cle in ('layout', 'horodatage', 'base_empreinte')}


def _valider(corps):
    if not isinstance(corps, dict):
        raise BrouillonRefuse('Un objet est attendu en corps.', 'detail')
    layout = corps.get('layout')
    if not isinstance(layout, dict):
        raise BrouillonRefuse(
            'Le brouillon doit porter le document de conception (objet).',
            'layout')
    for champ, maxi in (('horodatage', 40), ('base_empreinte', 64)):
        valeur = corps.get(champ)
        if not isinstance(valeur, str) or len(valeur) > maxi:
            raise BrouillonRefuse(
                f'« {champ} » : un texte d\'au plus {maxi} caractères est '
                'attendu.', champ)
    for champ in ('layout', 'horodatage', 'base_empreinte'):
        # Même refus que ``layout.enregistrer_layout`` : NUL / demi-substitut.
        chemin = _chemin_caractere_interdit(corps.get(champ), champ)
        if chemin:
            raise BrouillonRefuse(
                '« %s » contient un caractere interdit (caractere nul ou '
                'illisible) : corrigez la saisie.' % chemin, champ,
                conflit=True)
    return {'layout': layout, 'horodatage': corps['horodatage'],
            'base_empreinte': corps['base_empreinte']}


def _ecrire(calepinage, user, entree):
    from ..models import Calepinage

    with transaction.atomic():
        brouillons = dict(Calepinage.objects.select_for_update().filter(
            pk=calepinage.pk).values_list('brouillons_atelier',
                                          flat=True).first() or {})
        if entree is None:
            brouillons.pop(_cle(user), None)
        else:
            brouillons[_cle(user)] = entree
        # update() : ni save() ni signaux — updated_at et journal intacts.
        Calepinage.objects.filter(pk=calepinage.pk).update(
            brouillons_atelier=brouillons)
    calepinage.brouillons_atelier = brouillons


def enregistrer_brouillon(calepinage, user, corps):
    """Range le brouillon de ``user`` et le rend (forme du contrat)."""
    entree = _valider(corps)
    _ecrire(calepinage, user, entree)
    return dict(entree)


def effacer_brouillon(calepinage, user):
    """Efface le brouillon de ``user`` (idempotent)."""
    _ecrire(calepinage, user, None)
