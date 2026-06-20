"""Endpoint PUBLIC (sans login) servant le PDF CLIENT d'un devis/facture.

Accès uniquement via un jeton ShareLink long, imprévisible et expirant (30 j).
Le PDF servi est le PDF CLIENT — jamais de prix d'achat ni de marge (le moteur
premium ne les rend pas). Aucune autre donnée n'est atteignable depuis ce lien.

Protections (L855) : chaque réponse publique porte « X-Robots-Tag: noindex »
pour rester hors des moteurs de recherche, et l'accès est limité en débit par
IP + jeton (throttle cache-based, sans dépendance externe ni rendu modifié).
"""
from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import (
    api_view, permission_classes, throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from .models import ShareLink
from .quote_engine import clean_pdf_options, generate_premium_devis_pdf
from .utils.pdf import download_pdf, generate_facture_pdf


# Avis FR clair montré quand le lien est expiré ou introuvable. Aucune donnée
# interne n'est exposée : le client est simplement invité à demander un lien
# frais à TAQINOR (L854).
LINK_EXPIRED_MESSAGE = (
    "Ce lien de partage a expiré ou n'est plus valide. "
    "Merci de demander un nouveau lien à TAQINOR pour consulter votre document."
)


class PublicLinkRateThrottle(SimpleRateThrottle):
    """Limite le débit des liens publics par IP + jeton (cache-based).

    Pas de dépendance externe : on s'appuie sur le throttle DRF intégré et le
    cache du projet. Le taux est fixé ici (pas de réglage settings nécessaire)
    pour décourager le balayage de jetons et l'aspiration de PDF, sans jamais
    bloquer un client légitime qui consulte son document.
    """
    scope = 'public_sharelink'
    rate = '30/minute'

    def get_rate(self):
        # Taux fixé inline : pas besoin d'entrée DEFAULT_THROTTLE_RATES.
        return self.rate

    def get_cache_key(self, request, view):
        token = (view.kwargs or {}).get('token', '') if view else ''
        ident = self.get_ident(request)
        return self.cache_format % {
            'scope': self.scope,
            'ident': f'{ident}:{token}',
        }


def _noindex(response):
    """Marque une réponse publique comme non-indexable par les moteurs."""
    response['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
    return response


def _not_found():
    return _noindex(Response(
        {'detail': LINK_EXPIRED_MESSAGE},
        status=status.HTTP_404_NOT_FOUND,
    ))


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([PublicLinkRateThrottle])
def public_document(request, token):
    link = (
        ShareLink.objects
        .select_related('devis', 'facture', 'company')
        .filter(token=token)
        .first()
    )
    if link is None or not link.is_valid:
        return _not_found()

    try:
        if link.devis_id:
            # ERR74 — public share link is a safe GET: render + stream without
            # persisting fichier_pdf on every access (persist=False).
            key = generate_premium_devis_pdf(
                link.devis_id, clean_pdf_options({}), persist=False)
            pdf_bytes = download_pdf(key)
            filename = f'Devis_{link.devis.reference}.pdf'
        elif link.facture_id:
            facture = link.facture
            key = facture.fichier_pdf or generate_facture_pdf(facture.id)
            pdf_bytes = download_pdf(key)
            filename = f'Facture_{facture.reference}.pdf'
        else:
            return _not_found()
    except Exception:
        return _noindex(Response(
            {'detail': 'Document indisponible pour le moment.'},
            status=status.HTTP_404_NOT_FOUND,
        ))

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return _noindex(response)
