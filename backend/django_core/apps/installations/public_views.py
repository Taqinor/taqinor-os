"""Vues publiques tokenisées de l'app Installations (SANS LOGIN)."""
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from .models import Intervention


class PublicTokenThrottle(SimpleRateThrottle):
    """Throttle des pages publiques tokenisées d'intervention (XFSM7/ZFSM2) —
    protège le jeton contre le brute-force. Clé par (IP, token)."""
    scope = 'installations_public_token'

    def get_cache_key(self, request, view):
        kwargs = getattr(view, 'kwargs', None) or (
            request.resolver_match.kwargs if request.resolver_match else {})
        ident = f"{self.get_ident(request)}:{kwargs.get('token', '')}"
        return self.cache_format % {'scope': self.scope, 'ident': ident}

    def get_rate(self):
        return '30/min'


class InterventionLienClientPublicView(APIView):
    """XFSM7 — page publique tokenisée « technicien en route » : statut
    courant, technicien (nom + avatar), fenêtre promise (XFSM5) et ETA
    indicative. Token inconnu, révoqué ou expiré → 404 (jamais 403 : on ne
    confirme pas l'existence du token à un tiers). Read-only : aucune donnée
    interne (coûts, autres chantiers, etc.) n'entre dans le payload."""
    permission_classes = [AllowAny]
    throttle_classes = [PublicTokenThrottle]

    def get(self, request, token):
        interv = (
            Intervention.objects
            .select_related('installation', 'technicien')
            .filter(lien_client_token=token).first())
        if interv is None or interv.lien_client_expire:
            return Response(
                {'detail': 'Lien invalide ou expiré.'},
                status=status.HTTP_404_NOT_FOUND)
        from .selectors import intervention_public_payload
        return Response(intervention_public_payload(interv))


class InterventionRapportPublicView(APIView):
    """ZFSM2 — page publique tokenisée du compte-rendu d'intervention signé
    (F19) : photos avant/après, réserves, matériel consommé SANS prix
    d'achat ni marge, signature, + lien de téléchargement PDF. Token inconnu
    ou révoqué → 404 (jamais 403 : on ne confirme pas l'existence du token à
    un tiers). Read-only, aucune donnée interne."""
    permission_classes = [AllowAny]
    throttle_classes = [PublicTokenThrottle]

    def get(self, request, token):
        interv = (
            Intervention.objects
            .select_related('installation')
            .filter(lien_rapport_token=token).first())
        if interv is None:
            return Response(
                {'detail': 'Lien invalide ou expiré.'},
                status=status.HTTP_404_NOT_FOUND)
        from .selectors import intervention_rapport_public_payload
        return Response(intervention_rapport_public_payload(interv))


class InterventionRapportPdfPublicView(APIView):
    """ZFSM2 — téléchargement du PDF du compte-rendu signé, via le MÊME jeton
    public que la page ci-dessus. Réutilise le rendu F19 existant
    (`intervention_pdf.compte_rendu_pdf`) — aucune donnée interne."""
    permission_classes = [AllowAny]
    throttle_classes = [PublicTokenThrottle]

    def get(self, request, token):
        interv = (
            Intervention.objects
            .filter(lien_rapport_token=token).first())
        if interv is None:
            return Response(
                {'detail': 'Lien invalide ou expiré.'},
                status=status.HTTP_404_NOT_FOUND)
        from django.http import HttpResponse

        from . import intervention_pdf
        pdf_bytes = intervention_pdf.compte_rendu_pdf(interv)
        resp = HttpResponse(pdf_bytes, content_type='application/pdf')
        resp['Content-Disposition'] = (
            f'inline; filename="compte-rendu-intervention-{interv.id}.pdf"')
        return resp
