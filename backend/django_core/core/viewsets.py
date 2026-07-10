"""Viewset de base transverse de la couche fondation ``core``.

ARC2 — ``CompanyScopedModelViewSet`` : le viewset de base UNIQUE
----------------------------------------------------------------

Constat : ``TenantMixin`` (``core.mixins``) scope le queryset générique à
``request.user.company``, mais seuls ~21/649 ViewSets l'adoptaient, et 162
``perform_create`` re-codaient le forçage de ``company`` à la main dans 54
fichiers (``apps/crm/views.py`` re-codait même son propre scoping). Ce module
promeut un point d'entrée unique : un ``ModelViewSet`` qui porte déjà
``TenantMixin`` et expose des points d'extension NOMMÉS (non implémentés ici)
pour composer, quand ils atterriront, la pagination transverse (YAPIC1) et les
backends de filtre transverses (YAPIC2).

Détection automatique par le sweep d'isolation (YRBAC12)
--------------------------------------------------------

``core.tenant_isolation_scan.discover_tenant_viewsets`` découvre chaque
``ModelViewSet`` concret dont le MRO contient une classe nommée ``TenantMixin``
(``base.__name__ == "TenantMixin"``). Comme ``CompanyScopedModelViewSet`` hérite
de ``TenantMixin``, TOUT viewset converti à cette base est AUTOMATIQUEMENT
couvert par le test générique d'isolation multi-tenant
(``core.tests.test_tenant_isolation_sweep``) — sans branchement manuel.

``core`` reste FONDATION : ce module n'importe AUCUNE app domaine (seulement
``rest_framework`` et ``core.mixins``).
"""
from __future__ import annotations

from rest_framework import viewsets

from .mixins import TenantMixin

__all__ = ["CompanyScopedModelViewSet"]


class CompanyScopedModelViewSet(TenantMixin, viewsets.ModelViewSet):
    """``ModelViewSet`` scopé société — la base transverse unique (ARC2).

    Hérite de ``TenantMixin`` : ``get_queryset`` filtre sur
    ``request.user.company`` et ``perform_create``/``perform_update`` forcent la
    société côté serveur (jamais lue du corps de la requête). Un viewset domaine
    qui a besoin d'un filtrage SUPPLÉMENTAIRE (portée de visibilité, filtres de
    requête, ``select_related``…) ou d'un ``created_by`` en plus surcharge
    ``get_queryset``/``perform_create`` en appelant ``super()`` — le
    comportement d'isolation reste garanti et les réponses restent identiques.

    Points d'extension NOMMÉS (YAPIC1 / YAPIC2)
    -------------------------------------------
    Deux crochets de composition sont RÉSERVÉS pour les lots à venir ; ils ne
    changent RIEN au comportement tant qu'ils ne sont pas branchés :

    * ``pagination_class`` (YAPIC1) — laissé au défaut DRF
      (``DEFAULT_PAGINATION_CLASS`` du projet). Quand la pagination transverse
      atterrira, elle se posera ICI, en un seul endroit.
    * ``filter_backends`` (YAPIC2) — non surchargé ici (défaut DRF, vide sauf
      réglage projet). Quand les backends de filtre transverses atterriront,
      ils se composeront ICI.

    Ne rien poser sur ces attributs aujourd'hui garantit un comportement
    BYTE-IDENTIQUE au ``TenantMixin + ModelViewSet`` d'origine pour chaque
    pilote converti.
    """

    # YAPIC1 — point d'extension pagination transverse (non implémenté ici :
    # None ⇒ défaut projet DEFAULT_PAGINATION_CLASS, comportement inchangé).
    # YAPIC2 — point d'extension backends de filtre transverses (non implémenté
    # ici : défaut DRF, comportement inchangé). Un pilote qui déclare son propre
    # ``filter_backends`` (ex. SearchFilter/OrderingFilter) le conserve tel quel.
