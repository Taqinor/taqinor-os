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
from .models import Ticket
from .query_params import ENTIER_ID, choix_param, entier_param, valeur_param

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


def _enum_ou_vide(valeurs):
    """Schéma publié d'un paramètre à valeurs fermées : ``choix_param`` lit une
    valeur vide comme « absent », le schéma le dit."""
    return {'type': 'string', 'enum': [*valeurs, '']}


@extend_schema(
    parameters=[
        OpenApiParameter('q', {'type': 'string', 'maxLength': Q_MAX},
                         OpenApiParameter.QUERY, required=False,
                         description='Référence, nom du client ou numéro de série.'),
        OpenApiParameter('statut', _enum_ou_vide(Ticket.Statut.values),
                         OpenApiParameter.QUERY, required=False),
        OpenApiParameter('priorite', _enum_ou_vide(Ticket.Priorite.values),
                         OpenApiParameter.QUERY, required=False),
        OpenApiParameter('client', ENTIER_ID, OpenApiParameter.QUERY, required=False),
        OpenApiParameter('equipement', ENTIER_ID, OpenApiParameter.QUERY, required=False),
        OpenApiParameter('retard_sla', _enum_ou_vide(('true', 'false')),
                         OpenApiParameter.QUERY, required=False),
        OpenApiParameter('limite', {'type': 'integer', 'minimum': 1,
                                    'maximum': lectures.LIMITE_TICKETS_MAX},
                         OpenApiParameter.QUERY, required=False),
    ],
    responses=OpenApiTypes.OBJECT)
@api_view(['GET'])
@permission_classes([HasPermissionOrLegacy('sav_voir')])
def tickets_a_traiter(request):
    """SAV3 — ``GET /api/django/sav/assistant/tickets/`` : les tickets SAV en
    lignes compactes (ouverts non annulés par défaut, retard de SLA d'abord).
    Contrat ``contract_samples/assistant_tickets.json``."""
    _societe_ou_400(request)
    q = _texte_cherche(request, obligatoire=False)
    statut = choix_param(request, 'statut', Ticket.Statut.values, '')
    retard = choix_param(request, 'retard_sla', ('true', 'false'), '')
    limite = entier_param(request, 'limite', lectures.LIMITE_TICKETS_DEFAUT,
                          mini=1, maxi=lectures.LIMITE_TICKETS_MAX)
    total, lignes = lectures.tickets_compacts(
        request.user, q=q, statut=statut, limite=limite,
        priorite=choix_param(request, 'priorite', Ticket.Priorite.values, ''),
        client=entier_param(request, 'client'),
        equipement=entier_param(request, 'equipement'),
        retard_sla=None if not retard else retard == 'true')
    return Response({'q': q, 'statut': statut, 'total': total, 'limite': limite,
                     'lignes': lignes, 'lien': lectures.LIEN_FILE_SAV})
