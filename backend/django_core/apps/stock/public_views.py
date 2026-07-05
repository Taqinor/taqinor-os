"""Endpoint PUBLIC (sans login) — portail fournisseur en lecture seule
(XPUR22).

Accès uniquement via le jeton ``PortailFournisseurToken`` (long,
imprévisible, révocable/expirant — mêmes garanties que
``ventes.ShareLink``/``sav.Ticket.share_token``). Un jeton donne accès aux
documents d'UN SEUL fournisseur — jamais ceux d'un autre fournisseur, jamais
de marge. Le fournisseur peut :
  * consulter ses BCF en cours, réceptions, factures (statut de paiement) ;
  * confirmer un BCF + proposer une date d'arrivée (préserve la date
    demandée d'origine — OTD, XPUR7).

Protections : X-Robots-Tag noindex sur chaque réponse ; throttle cache-based
par IP + jeton (sans dépendance externe).
"""
from rest_framework import status
from rest_framework.decorators import (
    api_view, permission_classes, throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle


class PortailFournisseurThrottle(SimpleRateThrottle):
    """Limite le débit du portail fournisseur par IP + jeton (cache-based,
    sans dépendance externe)."""
    scope = 'stock_portail_fournisseur'
    rate = '30/minute'

    def get_rate(self):
        return self.rate

    def get_cache_key(self, request, view):
        token = (view.kwargs or {}).get('token', '')
        ident = self.get_ident(request)
        return self.cache_format % {
            'scope': self.scope, 'ident': f'{ident}:{token}',
        }


def _noindex(response):
    response['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
    return response


def _not_found():
    return _noindex(Response(
        {'detail': "Ce lien du portail fournisseur est invalide, révoqué "
                   "ou expiré."},
        status=status.HTTP_404_NOT_FOUND,
    ))


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([PortailFournisseurThrottle])
def portail_fournisseur_documents_view(request, token):
    """XPUR22 — documents (BCF/réceptions/factures) DU SEUL fournisseur
    porteur de ce jeton. 404 sans fuite de données si le jeton est invalide,
    révoqué ou expiré."""
    from .services import (
        resoudre_token_portail_fournisseur, portail_fournisseur_documents,
    )
    token_obj = resoudre_token_portail_fournisseur(token)
    if token_obj is None:
        return _not_found()
    return _noindex(Response(portail_fournisseur_documents(token_obj)))


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PortailFournisseurThrottle])
def portail_fournisseur_confirmer_bcf_view(request, token, bcf_id):
    """XPUR22 — le fournisseur confirme un BCF et propose une date
    d'arrivée. Corps : ``{"date_confirmee_fournisseur": "YYYY-MM-DD",
    "numero_confirmation_fournisseur": "..."}``. Isolation stricte : le BCF
    doit appartenir au fournisseur porteur du jeton (sinon 404, jamais
    d'accès croisé)."""
    from .services import (
        resoudre_token_portail_fournisseur, confirmer_bcf_portail_fournisseur,
    )
    token_obj = resoudre_token_portail_fournisseur(token)
    if token_obj is None:
        return _not_found()

    date_confirmee = request.data.get('date_confirmee_fournisseur')
    if not date_confirmee:
        return _noindex(Response(
            {'detail': 'date_confirmee_fournisseur est requise.'},
            status=status.HTTP_400_BAD_REQUEST))

    try:
        bc = confirmer_bcf_portail_fournisseur(
            token_obj, bcf_id, date_confirmee=date_confirmee,
            numero_confirmation=request.data.get(
                'numero_confirmation_fournisseur', ''))
    except ValueError:
        return _not_found()

    return _noindex(Response({
        'id': bc.id, 'reference': bc.reference,
        'date_confirmee_fournisseur': bc.date_confirmee_fournisseur,
        'numero_confirmation_fournisseur':
            bc.numero_confirmation_fournisseur,
    }))
