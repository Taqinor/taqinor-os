"""Selectors du module Appels d'offres (``apps.ao``).

Point d'entrée des LECTURES cross-app du domaine AO (CLAUDE.md : les autres
apps lisent ``ao`` via ``apps.ao.selectors`` ou par string-FK, jamais via
``apps.ao.models``).

AOF17 — le lien AO ↔ lead, SANS couplage
----------------------------------------
``AppelOffre.lead_id`` est un ``PositiveIntegerField`` OPAQUE, PAS une FK vers
``crm.Lead`` — et c'est délibéré : c'est exactement ce qui tient le contrat
import-linter ``ao-models-decoupled`` (``apps.ao.models`` n'importe AUCUN
``models`` du cœur métier). Un agent bien intentionné voudra un jour le
« réparer » en vraie FK : **c'est interdit**, et un test le verrouille
(``apps/ao/tests/test_lien_crm.py``).

Conséquence pratique : le CRM liste les AO d'un lead par ``ao_par_lead`` (ici),
et ``ao`` lit le lead par ``crm.selectors`` (jamais ``crm.models``).
"""
from __future__ import annotations


def ao_par_lead(company, lead_id):
    """Les appels d'offres d'un lead, bornés à la société (lecture seule).

    Point d'entrée cross-app : le CRM affiche « les AO de ce lead » sans jamais
    importer ``apps.ao.models``. Un ``lead_id`` vide renvoie un queryset VIDE
    (jamais tous les AO de la société — un filtre absent ne doit pas se muer en
    absence de filtre).
    """
    from .models import AppelOffre

    if not lead_id:
        return AppelOffre.objects.none()
    return AppelOffre.objects.filter(company=company, lead_id=lead_id)


def compte_ao_par_lead(company, lead_id):
    """Nombre d'AO rattachés à un lead (badge CRM), borné à la société."""
    return ao_par_lead(company, lead_id).count()


def fiche_lead_de_l_ao(appel_offre):
    """Fiche-carte LECTURE SEULE du lead lié, ou ``None``.

    Passe par ``apps.crm.selectors.lead_card`` — jamais ``apps.crm.models``.
    """
    if not appel_offre.lead_id:
        return None
    from apps.crm.selectors import lead_card

    return lead_card(appel_offre.lead_id, appel_offre.company)
