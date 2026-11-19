"""Copilote vague 2 — vues SAV servies à l'assistant (actions ``sav.*``).

Ces routes sont internes : leur seul consommateur est le relais FastAPI de
l'assistant (JWT de l'utilisateur relayé ; permission, société et portée
re-vérifiées ICI). Les lectures rendent les formes compactes des échantillons
``contract_samples/assistant_*.json``, construites par ``selectors_assistant``.

Fichier à part : ``views.py`` dépasse 2 000 lignes et ne grossit plus.
"""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.permissions import HasPermissionOrLegacy

from . import selectors_assistant as lectures
from .query_params import entier_param, valeur_param

#: Longueur maximale du texte cherché (nom, téléphone, numéro de série).
Q_MAX = 100


def _societe_ou_400(request):
    if getattr(request.user, 'company_id', None) is None:
        raise ValidationError({'detail': 'Utilisateur sans société.'})


def _texte_cherche(request, obligatoire):
    """``q`` borné ; 400 nommant le paramètre s'il manque (``obligatoire``) ou
    dépasse ``Q_MAX`` caractères."""
    q = (valeur_param(request, 'q') or '').strip()
    if obligatoire and not q:
        raise ValidationError({'q': [
            'Texte obligatoire : nom, téléphone ou numéro de série du client.']})
    if len(q) > Q_MAX or '\x00' in q:
        raise ValidationError({'q': [
            f'Texte de {Q_MAX} caractères au plus, sans caractère nul.']})
    return q


@extend_schema(
    parameters=[
        OpenApiParameter('q', {'type': 'string', 'minLength': 1, 'maxLength': Q_MAX},
                         OpenApiParameter.QUERY, required=True,
                         description='Nom, téléphone ou numéro de série.'),
        OpenApiParameter('limite', {'type': 'integer', 'minimum': 1,
                                    'maximum': lectures.LIMITE_PARC_MAX},
                         OpenApiParameter.QUERY, required=False),
    ],
    responses=OpenApiTypes.OBJECT)
@api_view(['GET'])
@permission_classes([HasPermissionOrLegacy('sav_voir')])
def parc_client(request):
    """SAV2 — ``GET /api/django/sav/assistant/parc/`` : le parc d'un client
    (chantiers, équipements et garantie effective, tickets ouverts, contrat
    actif). Contrat ``contract_samples/assistant_parc.json``."""
    _societe_ou_400(request)
    q = _texte_cherche(request, obligatoire=True)
    limite = entier_param(request, 'limite', lectures.LIMITE_PARC_DEFAUT,
                          mini=1, maxi=lectures.LIMITE_PARC_MAX)
    total, clients = lectures.parc_clients(request.user, q, limite)
    return Response({'q': q, 'total': total, 'limite': limite, 'clients': clients})
