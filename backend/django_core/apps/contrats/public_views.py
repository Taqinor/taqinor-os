"""Endpoints PUBLICS (sans login) du portail client — section « Mes contrats
& abonnements » (XCTR14).

Le client s'identifie par le token du portail self-service EXISTANT
(``compta.ComptePortailClient``, FG228) — résolu par le sélecteur LECTURE
SEULE de l'app cible (``apps.compta.selectors.compte_portail_par_token``),
jamais un import de son modèle (frontière cross-app, CLAUDE.md). Le client ne
voit QUE ses propres contrats (filtrés par ``client_id`` — jamais un contrat
d'un autre client ou d'une autre société).

Données JAMAIS exposées ici : ``confidentialite``, ``responsable``, ou tout
champ interne — voir ``selectors.contrats_portail_client``. Les deux actions
« demander le renouvellement » / « demander la résiliation » NE changent
JAMAIS le statut du contrat (préservation des statuts — CONTRAT12) : elles
créent uniquement une activité/notification côté ERP.

Protections : X-Robots-Tag noindex sur chaque réponse publique ; throttle
cache-based par IP (30 req/min), même patron que ``sav.public_views`` /
``ventes.public_views``.
"""
from rest_framework import status
from rest_framework.decorators import (
    api_view, permission_classes, throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from . import selectors, services
from .models import Contrat


class ContratsPortailThrottle(SimpleRateThrottle):
    """Limite le débit du portail contrats par IP (cache-based, sans dépendance)."""
    scope = 'contrats_portail'
    rate = '30/minute'

    def get_rate(self):
        return self.rate

    def get_cache_key(self, request, view):
        ident = self.get_ident(request)
        return self.cache_format % {'scope': self.scope, 'ident': ident}


def _noindex(response):
    response['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
    return response


def _not_found():
    return _noindex(Response(
        {'detail': "Ce lien de portail est invalide ou n'existe pas."},
        status=status.HTTP_404_NOT_FOUND,
    ))


def _resoudre_compte(token):
    """Résout le compte portail par token via le sélecteur de ``compta``.

    Frontière cross-app : jamais un import de ``compta.models`` — uniquement
    son sélecteur de lecture. Renvoie ``None`` si l'app compta est absente ou
    le token invalide (dégradation propre)."""
    try:
        from apps.compta.selectors import compte_portail_par_token
    except Exception:  # pragma: no cover - app compta absente
        return None
    return compte_portail_par_token(token)


def _serialize_row(row):
    return {
        'id': row['id'],
        'reference': row['reference'],
        'objet': row['objet'],
        'type_contrat': row['type_contrat'],
        'statut': row['statut'],
        'statut_display': row['statut_display'],
        'date_debut': row['date_debut'].isoformat() if row['date_debut'] else None,
        'date_fin': row['date_fin'].isoformat() if row['date_fin'] else None,
        'montant': str(row['montant']),
        'devise': row['devise'],
        'prochaine_echeance': (
            row['prochaine_echeance'].isoformat()
            if row['prochaine_echeance'] else None),
        'factures_ids': row['factures_ids'],
    }


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([ContratsPortailThrottle])
def portail_mes_contrats(request, token):
    """XCTR14 — Liste des contrats du client portail (lecture seule).

    GET /api/django/public/contrats/portail/<token>/

    Résout le compte portail par token (404 si invalide/inconnu — pas de fuite
    d'existence). Renvoie UNIQUEMENT les contrats du client résolu, jamais
    ceux d'un autre client ou d'une autre société.
    """
    compte = _resoudre_compte(token)
    if compte is None:
        return _not_found()

    rows = selectors.contrats_portail_client(compte.company, compte.client_id)
    return _noindex(Response({
        'count': len(rows),
        'results': [_serialize_row(r) for r in rows],
    }))


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([ContratsPortailThrottle])
def portail_demande_contrat(request, token, contrat_id):
    """XCTR14 — Demande 1-clic « renouvellement » / « résiliation ».

    POST /api/django/public/contrats/portail/<token>/<contrat_id>/demande/
    body: {"type": "renouvellement"|"resiliation", "message": str (optionnel)}

    Le contrat DOIT appartenir au client résolu par le token (sinon 404 — pas
    de fuite). AUCUN changement de statut n'est appliqué : la demande crée une
    activité + une notification côté ERP (voir
    ``services.demander_action_portail``)."""
    compte = _resoudre_compte(token)
    if compte is None:
        return _not_found()

    try:
        contrat = Contrat.objects.get(
            id=contrat_id, company=compte.company, client_id=compte.client_id)
    except Contrat.DoesNotExist:
        return _not_found()

    type_demande = (request.data.get('type') or '').strip()
    message = (request.data.get('message') or '').strip()

    try:
        services.demander_action_portail(
            contrat, type_demande=type_demande, message=message)
    except services.DemandePortailError as exc:
        return _noindex(Response(
            {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST))

    return _noindex(Response({'ok': True}, status=status.HTTP_201_CREATED))
