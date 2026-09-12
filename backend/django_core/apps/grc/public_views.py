"""NTGRC2 — portail PUBLIC de dépôt et de suivi d'une demande de droit.

Loi 09-08 (CNDP) : toute personne peut exercer ses droits (accès,
rectification, effacement) SANS compte. Deux routes, non authentifiées,
throttlées et sans aucune donnée personnelle d'autrui :

* ``POST /api/django/grc/public/demande-droit/`` — dépose la demande. Crée
  une ``core.DataSubjectRequest`` au statut ``recue`` avec, en PREUVE, un
  horodatage SERVEUR + l'IP et le user-agent du déposant. Un honeypot
  (« ne pas remplir ») neutralise les robots sans les informer.
* ``GET /api/django/grc/public/demande-droit/{token}/`` — suit la demande par
  un jeton OPAQUE, distinct de l'identifiant réel (aucune énumération) :
  statut, date de dépôt et échéance légale de 30 jours. Jamais la donnée
  d'une autre personne, jamais un identifiant interne.

La société est désignée par son ``slug`` public : sans lui, une demande
n'appartiendrait à aucun tenant. Toute lecture est bornée à CETTE société —
aucun accès inter-tenant n'est possible, dans un sens comme dans l'autre.
"""
from __future__ import annotations

from rest_framework import status
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers as drf_serializers
from rest_framework.decorators import (
    api_view, permission_classes, throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from .services import (
    DELAI_LEGAL_JOURS, creer_demande_publique, suivi_demande_publique,
)


class DemandeDroitThrottle(AnonRateThrottle):
    """Anti-abus du dépôt public (le dépôt écrit en base)."""

    scope = 'grc_demande_droit'
    rate = '10/hour'

    def get_rate(self):
        return self.rate


class SuiviDemandeThrottle(AnonRateThrottle):
    """Anti-énumération du suivi (lecture seule, plus permissif)."""

    scope = 'grc_suivi_demande'
    rate = '60/hour'

    def get_rate(self):
        return self.rate


def _client_ip(request):
    """IP du déposant (proxy-aware, best-effort) — preuve de dépôt."""
    transmis = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if transmis:
        return transmis.split(',')[0].strip()[:45]
    return (request.META.get('REMOTE_ADDR') or '')[:45]


@extend_schema(request=inline_serializer('DemandeDroitRequete', {
    'societe': drf_serializers.CharField(),
    'identifiant': drf_serializers.CharField(),
    'type': drf_serializers.CharField(),
    'commentaire': drf_serializers.CharField(required=False),
}), responses=inline_serializer('DemandeDroitReponse', {
    'token': drf_serializers.CharField(),
    'echeance_legale': drf_serializers.DateField(required=False),
}))
@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([DemandeDroitThrottle])
def deposer_demande_droit(request):
    """Dépôt PUBLIC d'une demande de droit (loi 09-08).

    Corps : ``societe`` (slug, requis), ``identifiant`` (email ou téléphone de
    la personne, requis), ``type`` (``acces`` / ``effacement`` /
    ``rectification``, défaut ``acces``), ``ne_pas_remplir`` (honeypot).

    Les erreurs NOMMENT le champ fautif, en français.
    """
    donnees = request.data or {}

    # Honeypot : un robot remplit tous les champs. On répond « accepté » sans
    # rien écrire — jamais d'indice sur le piège.
    if (donnees.get('ne_pas_remplir') or '').strip():
        return Response({'statut': 'recue'},
                        status=status.HTTP_201_CREATED)

    slug = (donnees.get('societe') or '').strip()
    identifiant = (donnees.get('identifiant') or '').strip()
    type_demande = (donnees.get('type') or 'acces').strip()

    erreurs = {}
    if not slug:
        erreurs['societe'] = 'La société destinataire est obligatoire.'
    if not identifiant:
        erreurs['identifiant'] = (
            'Indiquez l\'email ou le téléphone de la personne concernée.')
    if erreurs:
        return Response(erreurs, status=status.HTTP_400_BAD_REQUEST)

    demande, erreur = creer_demande_publique(
        slug, identifiant, type_demande,
        ip=_client_ip(request),
        user_agent=(request.META.get('HTTP_USER_AGENT') or '')[:512],
    )
    if erreur:
        return Response(erreur, status=status.HTTP_400_BAD_REQUEST)

    return Response(
        {
            'token_suivi': demande.token_suivi,
            'statut': demande.statut,
            'delai_legal_jours': DELAI_LEGAL_JOURS,
        },
        status=status.HTTP_201_CREATED,
    )


@extend_schema(responses=inline_serializer('SuiviDemandeDroitReponse', {
    'statut': drf_serializers.CharField(),
    'date_depot': drf_serializers.DateTimeField(required=False),
    'echeance_legale': drf_serializers.DateField(required=False),
}))
@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([SuiviDemandeThrottle])
def suivre_demande_droit(request, token):
    """Suivi PUBLIC d'une demande par son jeton opaque.

    Ne renvoie QUE l'état d'avancement de CETTE demande : statut, date de
    dépôt, échéance légale. Jamais l'identifiant interne, jamais la donnée
    d'une autre personne, jamais le résultat détaillé de l'export.
    """
    suivi = suivi_demande_publique(token)
    if suivi is None:
        return Response(
            {'detail': 'Demande introuvable pour ce jeton de suivi.'},
            status=status.HTTP_404_NOT_FOUND)
    return Response(suivi)
