"""D-ACAL-169 — désigner / retirer LE panneau par défaut d'une société (écriture unique du drapeau).

Patron « un défaut par portée, posé par une action dédiée qui retire les autres dans la même transaction » :
``uxviews.SavedView.est_defaut_role`` (``apps/uxviews/views.py``). La société vient TOUJOURS de l'appelant (jamais du
corps de la requête) ; la ligne ``authentication.Company`` est verrouillée le temps du geste, si bien que deux gestes
simultanés ne laissent jamais deux défauts (la contrainte ``stock_produit_un_panneau_defaut_par_societe`` le garantit
de toute façon en base). Le geste ne RECALCULE rien : aucun devis, aucun calepinage, aucun choix automatique n'est
touché — les écritures passent par ``update()`` (ni signal, ni ``produit_modifie``, ni ``lock_version``).
"""
from __future__ import annotations

import logging

from django.db import transaction
from rest_framework.exceptions import ValidationError

from .selectors_panneau_defaut import est_un_panneau, resume_panneau_par_defaut

logger = logging.getLogger(__name__)

CHAMP = 'panneau_par_defaut'
REFUS_PAS_UN_PANNEAU = "« {nom} » n'est pas un panneau : seul un panneau peut être le panneau par défaut."
REFUS_ARCHIVE = "« {nom} » est archivé : désarchivez-le avant d'en faire le panneau par défaut."
REFUS_SANS_PRIX = "« {nom} » n'a pas de prix de vente : saisissez son prix avant d'en faire le panneau par défaut."


def _refus(produit):
    """La phrase de refus (sous le champ), ou ``None`` si le produit peut être le panneau par défaut."""
    from .etat_ci import _prix_vente_saisi

    if not est_un_panneau(produit):
        return REFUS_PAS_UN_PANNEAU.format(nom=produit.nom)
    if produit.is_archived:
        return REFUS_ARCHIVE.format(nom=produit.nom)
    if not _prix_vente_saisi(produit):
        return REFUS_SANS_PRIX.format(nom=produit.nom)
    return None


def _verrouiller_societe(company):
    from authentication.models import Company

    Company.objects.select_for_update().filter(pk=company.pk).first()


def definir_panneau_par_defaut(company, produit, user=None):
    """Fait de ``produit`` (de ``company``) LE panneau par défaut ; rend le résumé du contrat. 400 nommé sinon."""
    from .models import Produit

    if company is None or produit.company_id != company.pk:
        raise ValidationError({CHAMP: ["Ce produit n'appartient pas à votre société."]})
    motif = _refus(produit)
    if motif:
        raise ValidationError({CHAMP: [motif]})
    with transaction.atomic():
        _verrouiller_societe(company)
        (Produit.objects.filter(company=company, panneau_par_defaut=True)
         .exclude(pk=produit.pk).update(panneau_par_defaut=False))
        Produit.objects.filter(pk=produit.pk, company=company).update(panneau_par_defaut=True)
    logger.info('D-ACAL-169 : panneau par défaut de la société %s = produit %s (par %s)',
                company.pk, produit.pk, getattr(user, 'pk', None))
    return resume_panneau_par_defaut(company)


def retirer_panneau_par_defaut(company, produit, user=None):
    """Retire le drapeau de ``produit`` s'il le porte (idempotent) ; rend le résumé du contrat."""
    from .models import Produit

    with transaction.atomic():
        _verrouiller_societe(company)
        retire = Produit.objects.filter(
            pk=produit.pk, company=company, panneau_par_defaut=True).update(panneau_par_defaut=False)
    if retire:
        logger.info('D-ACAL-169 : panneau par défaut retiré (société %s, produit %s, par %s)',
                    company.pk, produit.pk, getattr(user, 'pk', None))
    return resume_panneau_par_defaut(company)
