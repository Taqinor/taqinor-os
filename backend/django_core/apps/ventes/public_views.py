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


# ── Q6/Q7 — Proposition WEB tokenisée (données JSON + e-signature) ────────────
# Même jeton ShareLink que le PDF public (long, imprévisible, expirant) ;
# borné à un devis donc company-scoped par construction (le jeton ne référence
# qu'un seul devis d'une seule société). Aucun login : le jeton AUTHENTIFIE.

def _client_ip(request):
    fwd = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return (fwd.split(',')[0].strip() or request.META.get('REMOTE_ADDR') or '')


def _resolve_proposal_link(token):
    """Return a valid devis-bearing ShareLink for this token, or None."""
    link = (
        ShareLink.objects
        .select_related('devis', 'devis__client', 'devis__company', 'company')
        .filter(token=token)
        .first()
    )
    if link is None or not link.is_valid or not link.devis_id:
        return None
    return link


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([PublicLinkRateThrottle])
def proposal_data(request, token):
    """Q6 — données JSON de la proposition pour le rendu web client (W116).

    Renvoie la sortie de ``build_quote_data`` + l'URL signée du rendu de
    toiture (si présent) + les totaux par option. Lecture seule, authentifiée
    par le jeton (pas de login), bornée au devis du jeton (donc à sa société) ;
    jeton expiré/invalide → 404 sans fuite."""
    link = _resolve_proposal_link(token)
    if link is None:
        return _not_found()
    try:
        from .quote_engine.builder import build_quote_data
        devis = link.devis
        data = build_quote_data(devis, {'pdf_mode': 'full'})
        roof_url = None
        if data.get('roof_image_key'):
            try:
                from .utils.pdf import roof_image_signed_url
                roof_url = roof_image_signed_url(data['roof_image_key'])
            except Exception:  # noqa: BLE001 — un rendu absent ne casse rien
                roof_url = None
        payload = {
            'reference': data['ref'],
            'date': data['date'],
            'client_name': data['client_name'],
            'statut': devis.statut,
            'quote': data,
            'roof_image_url': roof_url,
            'option_totals': {
                'sans_batterie': data.get('totaux_sans'),
                'avec_batterie': data.get('totaux_avec'),
                'display_total': data.get('display_total'),
                'nb_options': data.get('nb_options'),
            },
            # Le devis est-il déjà accepté ? (pilote l'UI e-signature)
            'accepted': devis.statut == 'accepte',
            'accepte_par_nom': data.get('accepte_par_nom') or '',
            'date_acceptation': data.get('date_acceptation') or '',
        }
    except Exception:  # noqa: BLE001
        return _noindex(Response(
            {'detail': 'Proposition indisponible pour le moment.'},
            status=status.HTTP_404_NOT_FOUND))
    return _noindex(Response(payload))


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PublicLinkRateThrottle])
def proposal_accept(request, token):
    """Q7 — e-signature : le client accepte la proposition via le jeton.

    Enregistre nom saisi + horodatage + IP dans le tampon d'acceptation
    existant (``accepte_par_nom``/``date_acceptation``) et bascule le devis en
    « accepté » À TRAVERS le service d'acceptation unique — la chaîne
    bon-commande/facture est donc préservée 1:1 (règle #4). Idempotent : un
    double envoi ne re-signe pas. Pas de login : le jeton authentifie."""
    link = _resolve_proposal_link(token)
    if link is None:
        return _not_found()
    devis = link.devis
    nom = (request.data.get('nom') or request.data.get('name') or '').strip()
    if not nom:
        return _noindex(Response(
            {'detail': 'Votre nom est requis pour signer la proposition.'},
            status=status.HTTP_400_BAD_REQUEST))
    option = (request.data.get('option') or '').strip()
    from .services import accept_devis, AcceptError
    try:
        accept_devis(
            devis=devis, user=None, nom=nom, option=option,
            ip=_client_ip(request))
    except AcceptError as exc:
        return _noindex(Response(
            {'detail': exc.message},
            status=(status.HTTP_409_CONFLICT if exc.conflict
                    else status.HTTP_400_BAD_REQUEST)))
    return _noindex(Response({
        'detail': 'Proposition acceptée. Merci !',
        'reference': devis.reference,
        'statut': devis.statut,
        'accepte_par_nom': devis.accepte_par_nom,
    }))
