"""NTPRT20/NTPRT27 — Tableaux de bord des portails FOURNISSEUR et PARTENAIRE.

Deux endpoints en LECTURE SEULE, symétriques du portail client :

* ``GET /api/django/portail/fournisseur/tableau-de-bord/``
* ``GET /api/django/portail/partenaire/tableau-de-bord/``

Chacun est gardé par la portée EXACTE correspondante
(``IsPortalFournisseurUser`` / ``IsPortalPartenaireUser``, NTPRT5+) : un compte
CLIENT — ou un compte portail d'une autre portée, ou un interne — est refusé.
La garde exige aussi un rattachement non nul, et les sélecteurs appelés exigent
le couple (société, entité) : un compte sans entité voit des compteurs à ZÉRO,
jamais les chiffres de la société entière.

Les lectures passent par ``stock.selectors`` / ``crm.selectors`` (jamais un
import de leurs ``models`` depuis portail — frontière cross-app CLAUDE.md).
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.roles.permissions import (
    IsPortalFournisseurUser, IsPortalPartenaireUser, portal_scope_id,
)


@api_view(['GET'])
@permission_classes([IsPortalFournisseurUser])
def tableau_de_bord_fournisseur(request):
    """NTPRT20 — cartes résumé du fournisseur connecté."""
    from apps.stock.selectors import resume_portail_fournisseur
    return Response(resume_portail_fournisseur(
        request.user.company, portal_scope_id(request.user)))


@api_view(['GET'])
@permission_classes([IsPortalPartenaireUser])
def tableau_de_bord_partenaire(request):
    """NTPRT27 — cartes résumé du partenaire connecté."""
    from apps.crm.selectors import resume_portail_partenaire
    return Response(resume_portail_partenaire(
        request.user.company, portal_scope_id(request.user)))
