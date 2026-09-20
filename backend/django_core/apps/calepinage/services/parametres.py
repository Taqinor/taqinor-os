"""CAL45 — écriture des réglages société du module Calepinage.

UNE base, sept extensions : chaque tâche suivante ÉTEND une section, elle ne
crée plus de modèle. Ce service est le SEUL chemin d'écriture des réglages —
l'endpoint ``PUT /api/django/calepinage/parametres/`` l'appellera, il ne
touchera jamais le modèle directement.

Deux refus explicites, en français et en NOMMANT la clé fautive :
  * une SECTION inconnue (on ne range pas un réglage dans un tiroir qui
    n'existe pas — le fondateur doit voir LAQUELLE) ;
  * une section qui n'est pas un objet.

La société est TOUJOURS celle passée par l'appelant (posée côté serveur),
jamais lue d'un corps de requête.
"""
from __future__ import annotations


class ReglageInvalide(ValueError):
    """Erreur métier : un réglage refusé, avec un message français.

    ``champ`` nomme la section fautive pour que l'écran puisse pointer LE
    champ concerné au lieu d'afficher un « non enregistré » générique.
    """

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ


def enregistrer_parametres(company, donnees, *, remplacer=False):
    """Pose les sections de ``donnees`` sur les réglages de ``company``.

    Args:
        company: la société — posée côté serveur, jamais lue de la requête.
        donnees: ``{section: objet}``. Les sections ABSENTES sont laissées
            telles quelles (mise à jour partielle) sauf si ``remplacer``.
        remplacer: ``True`` remet à ``{}`` les sections non fournies.

    Returns:
        Le dict complet des sept sections, comme le rend le sélecteur.

    Raises:
        ReglageInvalide: section inconnue, ou section qui n'est pas un objet.
    """
    from django.db import IntegrityError, transaction

    from ..models import ParametresCalepinage
    from ..selectors import SECTIONS_PARAMETRES, parametres_de_societe

    if company is None:
        raise ReglageInvalide(
            "Les réglages de calepinage sont toujours rattachés à une "
            "société : aucune société n'a été fournie.", champ='company')

    donnees = donnees or {}
    inconnues = ParametresCalepinage.sections_inconnues(donnees)
    if inconnues:
        raise ReglageInvalide(
            "Section de réglages inconnue : "
            f"« {', '.join(inconnues)} ». Sections admises : "
            f"{', '.join(SECTIONS_PARAMETRES)}.",
            champ=inconnues[0])

    for section, valeur in donnees.items():
        if not isinstance(valeur, dict):
            raise ReglageInvalide(
                f"La section « {section} » doit être un objet "
                f"(reçu : {type(valeur).__name__}).", champ=section)

    # CAL47 — une section peut avoir son PROPRE domaine de validité (contrat
    # CAL46 pour « imagerie »). Le crochet est ici, une fois : chaque section
    # qui se dote d'un normaliseur l'enregistre dans ``_normaliseurs()`` au lieu
    # d'ouvrir un second chemin d'écriture. Une section sans normaliseur passe
    # inchangée — comportement d'aujourd'hui, strictement préservé.
    donnees = _normaliser(donnees)

    with transaction.atomic():
        # `UniqueConstraint(['company'])` fait foi : on LIT d'abord, et si deux
        # requêtes concurrentes créent en même temps, la base tranche
        # (IntegrityError) et on relit la ligne gagnante — jamais deux jeux de
        # réglages pour une même société.
        reglages = ParametresCalepinage.objects.filter(
            company=company).order_by('id').first()
        if reglages is None:
            try:
                with transaction.atomic():
                    reglages = ParametresCalepinage.objects.create(
                        company=company)
            except IntegrityError:
                reglages = ParametresCalepinage.objects.filter(
                    company=company).order_by('id').first()
        for section in SECTIONS_PARAMETRES:
            if section in donnees:
                setattr(reglages, section, donnees[section])
            elif remplacer:
                setattr(reglages, section, {})
        reglages.full_clean(exclude=['company'])
        reglages.save()

    return parametres_de_societe(company)


def _normaliseurs():
    """``{section: normaliseur}`` — les sections qui ont leur propre domaine.

    Import FONCTION-LOCAL : ``services/site.py`` importe ``ReglageInvalide``
    de ce module ; le résoudre au chargement ferait un cycle.
    """
    from .degagements import (
        SECTION as SECTION_DEGAGEMENTS, normaliser_section_degagements,
    )
    from .site import SECTION as SECTION_IMAGERIE, normaliser_section_imagerie
    from .zones_reglementaires import (
        SECTION as SECTION_ZONES, normaliser_section_zones_types,
    )

    return {
        SECTION_IMAGERIE: normaliser_section_imagerie,
        SECTION_ZONES: normaliser_section_zones_types,
        SECTION_DEGAGEMENTS: normaliser_section_degagements,
    }


def _normaliser(donnees):
    """Applique le normaliseur de chaque section fournie qui en a un.

    Une section SANS normaliseur traverse inchangée : ajouter un domaine de
    validité à une section ne change RIEN aux six autres.
    """
    normaliseurs = _normaliseurs()
    concernees = [s for s in donnees if s in normaliseurs]
    if not concernees:
        return donnees
    donnees = dict(donnees)
    for section in concernees:
        donnees[section] = normaliseurs[section](donnees[section])
    return donnees
