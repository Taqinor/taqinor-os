"""Socle de ViewSets du module Appels d'offres (``apps.ao``) — AOF3.

Constat corrigé ici : les 8 ViewSets AO héritaient de ``_ComptaBaseViewSet``
(``TenantMixin`` + ``ModelViewSet`` + ``IsResponsableOrAdmin``). Deux
conséquences : ``scripts/check_platform.py`` refuse tout NOUVEAU ``ModelViewSet``
non basé sur ``CompanyScopedModelViewSet`` (SCA4), et surtout tout le palier
Responsable voyait l'intégralité d'un dossier d'appel d'offres alors qu'aucune
permission ``ao_*`` n'existait (régression de confidentialité, cf. AOF2).

``AoBaseViewSet`` = ``core.viewsets.CompanyScopedModelViewSet`` (scoping
``request.user.company`` + ``company`` forcée côté serveur, détection
automatique par le sweep d'isolation multi-tenant) + le chatter générique
``records`` (``ChatterViewSetMixin``, ARC8 — jamais une classe ``*Activity``
maison), gardé par ``ao_voir`` (lecture) / ``ao_gerer`` (écriture).

Composition des permissions
---------------------------
``ScopedPermission`` s'applique TOUJOURS (elle porte ``ao_voir``/``ao_gerer``),
et une ``@action`` qui déclare sa PROPRE garde la voit AJOUTÉE, jamais
substituée. C'est volontaire : les actions de chatter héritées de ``records``
déclarent ``IsAnyRole``/``IsResponsableOrAdmin``, or ces gardes-là
ROUVRIRAIENT sur le chatter d'un AO exactement la fuite que AOF2 ferme (un
Commercial lirait la timeline d'un dossier qu'il n'a pas le droit de voir). En
cumulant, la garde du domaine AO reste le plancher et la garde déclarée par
l'action reste un plafond supplémentaire — aucune déclaration n'est perdue en
silence (cf. ``core.permissions.declared_action_permissions``).
"""
from __future__ import annotations

from apps.records.views import ChatterViewSetMixin
from core.permissions import ScopedPermission, declared_action_permissions
from core.viewsets import CompanyScopedModelViewSet

from .permissions import AO_GERER, AO_VOIR

__all__ = ['AoBaseViewSet']


class AoBaseViewSet(ChatterViewSetMixin, CompanyScopedModelViewSet):
    """Base UNIQUE des ViewSets du domaine Appels d'offres.

    * société scopée + ``company`` posée côté serveur (jamais lue du corps) ;
    * lecture gardée par ``ao_voir``, écriture par ``ao_gerer`` ;
    * chatter générique ``records`` (``chatter/historique``, ``chatter/noter``).
    """

    read_permission = AO_VOIR
    write_permission = AO_GERER

    def get_permissions(self):
        permissions = [ScopedPermission()]
        declared = declared_action_permissions(self)
        if declared is not None:
            # CUMUL (jamais substitution) — voir le docstring du module.
            permissions.extend(declared)
        return permissions
