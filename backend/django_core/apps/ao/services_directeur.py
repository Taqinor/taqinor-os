"""AOF157 — services de l'ÉCONOMIE d'un appel d'offres (DIRECTEUR SEUL).

Module SÉPARÉ de ``apps.ao.services`` pour la même raison que les serializers
et les vues : un coût, une marge ou un bénéfice ne doivent JAMAIS se retrouver
par distraction dans un chemin consommé par une surface non-directeur.
"""
from __future__ import annotations

from decimal import Decimal

__all__ = ['creer_economie', 'nouvelle_cible']


def creer_economie(appel_offre, *, benefice_net_cible_ht=None, user=None,
                   motif='', arrondi_psychologique=None,
                   seuil_psychologique=None, ligne_ajustement=None, **champs):
    """Crée l'économie d'un AO (et sa première cible s'il y a une cible visée).

    L'arrondi, le SEUIL psychologique (la barre des 5 M en TTC) et la ligne
    d'ajustement appartiennent à la CIBLE, pas à l'économie : ils sont
    VERSIONNÉS avec elle, donc explicitement redirigés vers ``nouvelle_cible``
    au lieu de tomber dans ``**champs`` (où ils atterrissaient sur
    ``EconomieAO.objects.create()``, qui ne porte aucun de ces champs).
    ``**champs`` reste réservé aux vrais champs de l'économie (taux de TVA,
    note comptable, verrou).
    """
    from .models import EconomieAO

    economie = EconomieAO.objects.create(
        company=appel_offre.company, appel_offre=appel_offre, **champs)
    valeurs_de_cible = (benefice_net_cible_ht, arrondi_psychologique,
                        seuil_psychologique, ligne_ajustement)
    if any(valeur is not None for valeur in valeurs_de_cible):
        nouvelle_cible(
            economie,
            benefice_net_cible_ht=(benefice_net_cible_ht
                                   if benefice_net_cible_ht is not None
                                   else Decimal('0.00')),
            motif=motif, arrondi_psychologique=arrondi_psychologique,
            seuil_psychologique=seuil_psychologique,
            ligne_ajustement=ligne_ajustement, user=user)
    return economie


def nouvelle_cible(economie, *, benefice_net_cible_ht, motif='',
                   arrondi_psychologique=None, seuil_psychologique=None,
                   ligne_ajustement=None, user=None):
    """Ajoute une VERSION de cible financière et désactive la précédente.

    Chaque version porte son auteur, sa date et son motif : c'est ce qui
    permet de justifier un mouvement de prix sans reconstituer de mémoire.
    L'auteur est posé CÔTÉ SERVEUR, jamais lu d'un corps de requête.
    """
    from django.db import transaction

    from .models import CibleFinanciere

    with transaction.atomic():
        precedente = economie.cibles.filter(active=True).first()
        version = (precedente.version + 1) if precedente else 1
        if precedente is not None:
            precedente.active = False
            precedente.save(update_fields=['active', 'updated_at'])
        cible = CibleFinanciere.objects.create(
            company=economie.company, economie=economie, version=version,
            benefice_net_cible_ht=Decimal(str(benefice_net_cible_ht)),
            arrondi_psychologique=(
                arrondi_psychologique
                if arrondi_psychologique is not None
                else (precedente.arrondi_psychologique if precedente
                      else Decimal('0.00'))),
            seuil_psychologique=(
                seuil_psychologique
                if seuil_psychologique is not None
                else (precedente.seuil_psychologique if precedente else None)),
            ligne_ajustement=(
                ligne_ajustement
                if ligne_ajustement is not None
                else (precedente.ligne_ajustement if precedente else None)),
            active=True, auteur=user, motif=motif or '')
    _journaliser_cible(cible, precedente, user)
    return cible


def _journaliser_cible(cible, precedente, user):
    """Trace le mouvement au chatter générique ``records`` (best-effort).

    Le chatter est posé sur l'APPEL D'OFFRES : il est déjà scopé société et
    déjà gardé. Le MONTANT n'y figure pas — un chatter se lit avec ``ao_voir``,
    pas avec ``ao_rentabilite_voir``.
    """
    from apps.records.models import Activity
    from apps.records.services import log_activity

    log_activity(
        cible.economie.appel_offre, Activity.Kind.MODIFICATION, user=user,
        field='cible_financiere', field_label='Cible financière (directeur)',
        old_value=f'v{precedente.version}' if precedente else '',
        new_value=f'v{cible.version}', body=cible.motif or '',
        company=cible.company)
