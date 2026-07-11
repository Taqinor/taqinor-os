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

ARC55 — permission par DÉFAUT unifiée
--------------------------------------

Deux schémas de permission viewset coexistaient et se concurrençaient : la
paire ``ScopedPermission``/``WriteScopedPermissionMixin`` (``core.permissions``,
split lecture/écriture par méthode HTTP) et des classes de rôle ad hoc — chaque
nouveau viewset choisissait au hasard. ARC55 pose ``ScopedPermission`` comme
``permission_classes`` PAR DÉFAUT de la base : un viewset qui NE déclare NI
``read_permission``/``write_permission`` NI ``get_permissions``/
``permission_classes`` propres exige simplement un utilisateur authentifié
(``ScopedPermission`` sans code = « authentifié suffit », des deux côtés) —
STRICTEMENT équivalent au défaut projet ``IsAuthenticated``. Un viewset qui a
son propre ``get_permissions`` (comme les 3 pilotes) N'EST PAS affecté : DRF
appelle ``get_permissions`` et ne consulte jamais ``permission_classes`` — sa
matrice 401/403 reste IDENTIQUE.

Convention (playbook) : un NOUVEAU viewset scopé société hérite de
``CompanyScopedModelViewSet`` et exprime son contrôle d'accès de l'UNE de ces
façons, jamais un mélange ad hoc :
  * lecture/écriture par méthode HTTP → poser ``read_permission`` /
    ``write_permission`` (le défaut ``ScopedPermission`` les lit) ;
  * grain par action (ex. ``destroy`` admin-only) → surcharger
    ``get_permissions`` (prime sur le défaut, DRF standard) ;
  * cas simple « authentifié suffit » → ne rien poser (le défaut s'en charge).
Le grain FIN des rôles reste YRBAC3 (nommé, non dupliqué ici) ; la parité
front↔back reste YRBAC10.

``core`` reste FONDATION : ce module n'importe AUCUNE app domaine (seulement
``rest_framework``, ``core.mixins`` et ``core.permissions``).
"""
from __future__ import annotations

from rest_framework import viewsets

from .mixins import TenantMixin
from .permissions import ScopedPermission

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

    Permission par DÉFAUT (ARC55)
    -----------------------------
    ``permission_classes = [ScopedPermission]`` est le défaut unifié : sans
    ``read_permission``/``write_permission`` ni ``get_permissions`` propre, il
    exige un utilisateur authentifié (des deux côtés) — équivalent strict du
    défaut projet ``IsAuthenticated``. Un viewset qui surcharge
    ``get_permissions`` (comme les 3 pilotes ARC2) N'EST PAS affecté : DRF
    appelle ``get_permissions`` et ne consulte jamais ``permission_classes`` —
    sa matrice 401/403 est INCHANGÉE. Pour un contrôle lecture≠écriture,
    poser ``read_permission``/``write_permission`` (lus par ``ScopedPermission``)
    plutôt qu'une classe de rôle ad hoc.
    """

    # YAPIC1 — point d'extension pagination transverse (non implémenté ici :
    # None ⇒ défaut projet DEFAULT_PAGINATION_CLASS, comportement inchangé).
    # YAPIC2 — point d'extension backends de filtre transverses (non implémenté
    # ici : défaut DRF, comportement inchangé). Un pilote qui déclare son propre
    # ``filter_backends`` (ex. SearchFilter/OrderingFilter) le conserve tel quel.

    # ARC55 — permission par défaut unifiée. Sans read_permission/
    # write_permission ni get_permissions propre : « authentifié suffit »
    # (équivalent IsAuthenticated). Surchargé/ignoré dès qu'un viewset a son
    # propre get_permissions — les 3 pilotes ARC2 restent donc byte-identiques.
    permission_classes = [ScopedPermission]
