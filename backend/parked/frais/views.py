"""Vues du module Notes de frais (``apps.frais``) — ODX15.

Ré-export TRANSITOIRE des ViewSets qui vivent encore dans
``apps.compta.views`` : ils sont adossés à ``_ComptaBaseViewSet``
(``TenantMixin`` + ``ModelViewSet``) — scoping ``request.user.company``,
assignation forcée de ``company`` en ``perform_create``, accès
Responsable/Administrateur — et leurs actions de cycle de vie
(soumettre/valider/rejeter/rembourser) appellent ``apps.compta.services``,
qui garde le POSTING COMPTABLE (6143/4432/trésorerie) et le verrou de période
FG115. C'est exactement la frontière voulue par ODX15 : la SAISIE et le
RÉFÉRENTIEL des frais appartiennent à ``apps.frais``, l'ÉCRITURE reste à
``apps.compta``.

Ce module donne aux nouvelles routes ``/api/django/frais/…`` un point d'entrée
stable ; les anciennes routes ``/api/django/compta/…`` continuent de servir les
MÊMES classes (aucun client cassé). Le corps sera relogé ici plus tard.
"""

from apps.compta.views import (  # noqa: F401
    BaremeIndemniteViewSet,
    IndemniteChantierViewSet,
    NoteFraisViewSet,
    PlafondNoteFraisViewSet,
    RapportNoteFraisViewSet,
)

__all__ = [
    'BaremeIndemniteViewSet',
    'IndemniteChantierViewSet',
    'NoteFraisViewSet',
    'PlafondNoteFraisViewSet',
    'RapportNoteFraisViewSet',
]
