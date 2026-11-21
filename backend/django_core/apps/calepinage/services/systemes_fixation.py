"""ACAL558 — l'ÉCRITURE du catalogue de systèmes de fixation de la société.

Les lectures vivent dans ``catalogue_fixation.py`` (CALX358) ; ce fichier
crée, modifie et publie un système ET ses composants, à la forme du contrat
``contract_samples/calepinage_systemes_fixation.json`` (ACAL557).

* La société vient TOUJOURS de l'appelant : un ``company`` du corps est ignoré.
* Les refus sont ceux des modèles (``SystemeFixation.clean``,
  ``ComposantFixation.clean`` et ``catalogue_fixation.erreur_de_regle``),
  rendus sous le CHEMIN du champ (``provenance``, ``composants[1].source``,
  ``composants[0].regle``) pour que l'écran les pose sous le bon champ.
* L'écriture est ATOMIQUE : un composant refusé n'écrit aucun système.
* Aucun prix ici : le prix d'un composant reste celui du produit du stock.
"""
from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction

__all__ = [
    'SystemeRefuse', 'systeme_publie', 'liste_des_systemes',
    'creer_systeme', 'modifier_systeme',
]

#: Les champs du système que le corps peut porter (jamais ``company``).
CHAMPS_SYSTEME = ('code', 'libelle', 'fabricant', 'mode_pose', 'actif',
                  'provenance', 'couvertures',  # couvertures : ACAL566
                  'controles_pose')  # ACAL568
#: Les champs d'un composant que le corps peut porter (``ordre`` = son rang).
CHAMPS_COMPOSANT = ('role', 'libelle', 'unite', 'produit_id', 'regle',
                    'source')


class SystemeRefuse(Exception):
    """Refus NOMMÉ : ``erreurs`` = ``{chemin du champ: [message]}``."""

    def __init__(self, erreurs):
        super().__init__('Système de fixation refusé.')
        self.erreurs = erreurs


def systeme_publie(systeme):
    """Le système à la forme du contrat ACAL557, composants dans l'ordre."""
    from .catalogue_fixation import composants_du_systeme

    return {
        'id': systeme.pk, 'code': systeme.code, 'libelle': systeme.libelle,
        'fabricant': systeme.fabricant, 'mode_pose': systeme.mode_pose,
        'actif': systeme.actif, 'provenance': systeme.provenance,
        'couvertures': list(systeme.couvertures or []),
        'controles_pose': dict(systeme.controles_pose or {}),  # ACAL568
        'composants': [{
            'id': c.pk, 'role': c.role, 'libelle': c.libelle,
            'unite': c.unite, 'produit_id': c.produit_id,
            'regle': c.regle or {}, 'source': c.source, 'ordre': c.ordre,
        } for c in composants_du_systeme(systeme)],
    }


def liste_des_systemes(company):
    """``{systemes: [...]}`` — actifs ET désactivés (l'écran réactive)."""
    from ..models import SystemeFixation

    if company is None:
        return {'systemes': []}
    systemes = SystemeFixation.objects.filter(company=company).order_by(
        'libelle', 'id')
    return {'systemes': [systeme_publie(s) for s in systemes]}


def _messages(refus):
    return {champ: [str(m) for m in messages]
            for champ, messages in refus.message_dict.items()}


def _textes(valeurs, champs):
    """Un nombre saisi dans un champ texte est lu comme son texte."""
    return {cle: (str(v) if cle in champs and v is not None
                  and not isinstance(v, str) else v)
            for cle, v in valeurs.items()}


def _valider(instance, exclude):
    """Le refus du MODÈLE (``clean``) d'abord, puis celui des champs qu'il n'a
    pas déjà nommés : un champ ne porte jamais deux messages pour un manque."""
    erreurs = {}
    try:
        instance.clean()
    except ValidationError as refus:
        erreurs.update(_messages(refus))
    try:
        instance.clean_fields(exclude=list(exclude) + list(erreurs))
    except ValidationError as refus:
        erreurs.update(_messages(refus))
    return erreurs


def _valider_systeme(systeme, erreurs):
    from ..models import SystemeFixation

    from .catalogue_fixation import erreur_de_couvertures
    from .controles_pose import erreur_de_controles_pose

    erreurs.update(_valider(systeme, ['company', 'couvertures',
                                      'controles_pose']))
    if systeme.couvertures is None:
        systeme.couvertures = []
    if systeme.controles_pose is None:
        systeme.controles_pose = {}
    message_pose = erreur_de_controles_pose(systeme.controles_pose)
    if message_pose:
        erreurs['controles_pose'] = [message_pose]
    message = erreur_de_couvertures(systeme.couvertures)
    if message:
        erreurs['couvertures'] = [message]
    code = (systeme.code or '').strip()
    if code and 'code' not in erreurs and SystemeFixation.objects.filter(
            company=systeme.company, code=code).exclude(
                pk=systeme.pk).exists():
        erreurs['code'] = [
            'Un système de fixation porte déjà ce code dans la société.']


def _composants(corps, systeme, erreurs):
    """Les composants du corps, VALIDÉS (non enregistrés), ou ``None`` si la
    clé est absente (un PATCH sans ``composants`` garde la liste)."""
    from ..models import ComposantFixation

    if 'composants' not in corps:
        return None
    lignes = corps.get('composants')
    if not isinstance(lignes, list) or not all(
            isinstance(ligne, dict) for ligne in lignes):
        erreurs['composants'] = [
            'Les composants se saisissent en liste d’objets.']
        return []
    composants = []
    for rang, ligne in enumerate(lignes):
        champs = _textes({cle: ligne[cle] for cle in CHAMPS_COMPOSANT
                          if cle in ligne},
                         ('role', 'libelle', 'unite', 'source'))
        if champs.get('regle') is None:
            champs['regle'] = {}
        composant = ComposantFixation(company=systeme.company, ordre=rang,
                                      **champs)
        for champ, messages in _valider(composant,
                                        ['company', 'systeme']).items():
            erreurs[f'composants[{rang}].{champ}'] = messages
        composants.append(composant)
    return composants


def _enregistrer(systeme, corps):
    erreurs = {}
    saisis = _textes({cle: corps[cle] for cle in CHAMPS_SYSTEME
                      if cle in corps},
                     ('code', 'libelle', 'fabricant', 'mode_pose',
                      'provenance'))
    for champ, valeur in saisis.items():
        setattr(systeme, champ, valeur)
    _valider_systeme(systeme, erreurs)
    composants = _composants(corps, systeme, erreurs)
    if erreurs:
        raise SystemeRefuse(erreurs)
    with transaction.atomic():
        systeme.save()
        if composants is not None:
            systeme.composants.all().delete()
            for composant in composants:
                composant.systeme = systeme
                composant.save()
    return systeme


def creer_systeme(company, corps):
    """201 du contrat : le système créé, publié. ``company`` = l'appelant."""
    from ..models import SystemeFixation

    corps = corps if isinstance(corps, dict) else {}
    systeme = SystemeFixation(company=company)
    corps = dict(corps, composants=corps.get('composants', []))
    return systeme_publie(_enregistrer(systeme, corps))


def modifier_systeme(systeme, corps):
    """PATCH : les champs présents changent ; ``composants`` présent
    REMPLACE la liste (l'ordre est le rang dans la liste)."""
    corps = corps if isinstance(corps, dict) else {}
    return systeme_publie(_enregistrer(systeme, corps))
