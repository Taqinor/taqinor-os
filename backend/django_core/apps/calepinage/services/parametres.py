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
