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

from .models import PaymentLink, ShareLink
from .quote_engine import clean_pdf_options, generate_premium_devis_pdf
from .utils.pdf import download_pdf, generate_facture_pdf


# ── Profil saisonnier de production solaire au Maroc (T4) ────────────────────
# Poids mensuels (Jan…Déc) dérivés du GHI moyen marocain (apps/ventes/
# quote_engine/constants.py:GHI) puis NORMALISÉS pour sommer à 1. Sert UNIQUEMENT
# à répartir un total annuel RÉEL sur 12 mois quand seul l'annuel est connu —
# on ne fabrique jamais le total, on le distribue. Plus d'irradiance en été
# qu'en hiver, d'où des poids estivaux plus élevés.
_GHI_MONTHLY = [83.99, 96.79, 133.43, 155.30, 175.28, 179.62,
                179.56, 161.17, 137.03, 111.59, 81.91, 74.61]
_GHI_SUM = sum(_GHI_MONTHLY)
MOROCCO_SOLAR_MONTHLY_WEIGHTS = [round(g / _GHI_SUM, 6) for g in _GHI_MONTHLY]


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


def _monthly_production(data) -> list:
    """T4 — production solaire mensuelle (kWh/mois), 12 valeurs.

    Source : production annuelle RÉELLE du devis (``build_quote_data`` →
    ``prod_kwh``, qui reprend déjà l'étude/PVGIS stockée quand elle existe). On
    distribue ce total RÉEL via ``MOROCCO_SOLAR_MONTHLY_WEIGHTS`` (profil GHI
    Maroc normalisé). On ne fabrique jamais le total ; sans annuel → []."""
    annual = data.get('prod_kwh')
    try:
        annual = float(annual)
    except (TypeError, ValueError):
        return []
    if annual <= 0:
        return []
    return [round(annual * w) for w in MOROCCO_SOLAR_MONTHLY_WEIGHTS]


def _monthly_consumption(devis) -> list:
    """T4 — consommation mensuelle (kWh/mois) depuis les factures RÉELLES.

    Lit les factures du lead du devis via le sélecteur CRM (cross-app lecture
    seule, jamais d'import direct de ``apps.crm.models``). Convertit MAD→kWh
    avec le tarif INTERNE existant du projet (quote_engine.constants.KWH_PRICE),
    jamais un nouveau tarif codé en dur. Facture d'hiver toute l'année, ou
    hiver+été quand ``ete_differente`` (été = mois ~Mai→Oct). Sans facture → []
    (la page masque alors le graphe)."""
    from apps.crm.selectors import lead_bills_for_devis
    bills = lead_bills_for_devis(devis)
    if not bills:
        return []
    from .quote_engine.constants import KWH_PRICE
    if not KWH_PRICE:
        return []
    hiver_mad = bills['facture_hiver']
    ete_mad = bills['facture_ete']
    # Mois « été » (index 0=Jan) : Mai→Octobre. Le reste = hiver.
    ete_months = {4, 5, 6, 7, 8, 9}
    out = []
    for m in range(12):
        if (bills['ete_differente'] and ete_mad is not None
                and m in ete_months):
            mad = ete_mad
        else:
            mad = hiver_mad
        out.append(round(mad / KWH_PRICE))
    return out


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
            # T4 — séries mensuelles pour le graphe client (additif).
            # Production : annuel RÉEL réparti par le profil GHI Maroc.
            'monthly_production': _monthly_production(data),
            # Consommation : factures RÉELLES du lead (MAD→kWh, tarif interne),
            # [] sans facture → la page masque le graphe.
            'monthly_consumption': _monthly_consumption(devis),
        }
    except Exception:  # noqa: BLE001
        return _noindex(Response(
            {'detail': 'Proposition indisponible pour le moment.'},
            status=status.HTTP_404_NOT_FOUND))
    return _noindex(Response(payload))


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([PublicLinkRateThrottle])
def proposal_pdf(request, token):
    """Flux PDF CLIENT du devis derrière le jeton de proposition (W116).

    Réutilise telle quelle la logique de ``public_document`` (validation du
    jeton ShareLink via ``_resolve_proposal_link``, rendu premium sans
    persistance, X-Robots-Tag: noindex, 404 amical sur jeton invalide/expiré).
    Disposition « inline » pour un affichage direct dans le navigateur ;
    nom de fichier ``Devis_<reference>.pdf``. Lecture seule : aucun statut de
    devis n'est touché (règle #4 — le moteur ne fait que rendre)."""
    link = _resolve_proposal_link(token)
    if link is None:
        return _not_found()
    try:
        # ERR74 — GET sûr : rendu + flux sans persister fichier_pdf.
        key = generate_premium_devis_pdf(
            link.devis_id, clean_pdf_options({}), persist=False)
        pdf_bytes = download_pdf(key)
        filename = f'Devis_{link.devis.reference}.pdf'
    except Exception:  # noqa: BLE001 — jamais de fuite, 404 amical
        return _noindex(Response(
            {'detail': 'Document indisponible pour le moment.'},
            status=status.HTTP_404_NOT_FOUND))

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return _noindex(response)


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


# ── FG53 — Page publique « Payer en ligne » + webhook ────────────────────────
# Authentifiée par le jeton PaymentLink (long, imprévisible, expirant) ; bornée
# à une seule facture d'une seule société par construction. Aucun login. Aucune
# donnée interne (prix d'achat/marge) n'est jamais exposée.

def _resolve_payment_link(token, *, require_valid=True):
    link = (
        PaymentLink.objects
        .select_related('facture', 'facture__client', 'company')
        .filter(token=token)
        .first()
    )
    if link is None:
        return None
    if require_valid and not link.is_valid:
        return None
    return link


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([PublicLinkRateThrottle])
def pay_page(request, token):
    """FG53 — données minimales de la page publique de paiement.

    Lecture seule, authentifiée par le jeton. Renvoie la référence facture, le
    montant à payer et le statut du lien — jamais de prix d'achat ni de marge.
    Un lien payé renvoie statut='paye' (page de confirmation côté front)."""
    link = _resolve_payment_link(token, require_valid=False)
    if link is None:
        return _not_found()
    facture = link.facture
    return _noindex(Response({
        'reference': facture.reference,
        'client_name': str(facture.client) if facture.client_id else '',
        'montant': str(link.montant),
        'devise': 'MAD',
        'statut': link.statut,
        'paye': link.statut == PaymentLink.Statut.PAYE,
        'expire': not link.is_valid and link.statut != PaymentLink.Statut.PAYE,
    }))


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PublicLinkRateThrottle])
def pay_webhook(request, token):
    """FG53 — webhook : enregistre un Paiement quand le fournisseur confirme.

    Idempotent (un double appel ne crée pas deux paiements). Le fournisseur du
    lien valide d'abord la notification (verify_webhook) ; le défaut NoOp confirme
    en mode manuel. Aucune passerelle live n'est câblée — c'est le scaffold."""
    link = _resolve_payment_link(token, require_valid=False)
    if link is None:
        return _not_found()
    from .services import record_payment_from_link
    paiement, err = record_payment_from_link(link=link, payload=request.data)
    if err is not None:
        return _noindex(Response(
            {'detail': err}, status=status.HTTP_400_BAD_REQUEST))
    return _noindex(Response({
        'detail': 'Paiement enregistré. Merci !',
        'reference': link.facture.reference,
        'montant': str(paiement.montant),
        'statut': PaymentLink.Statut.PAYE,
    }))
