"""Paiement public : acompte de succès, virement déclaré, page et webhook de paiement (SPL252, déplacé de ``public_views.py``).

RIB de la société, bloc d'acompte renvoyé à la signature, déclaration de
virement (note chatter, aucun statut changé), page publique « Payer en ligne »
et webhook du prestataire (jeton ``PaymentLink``). Le suffixe ``_views.py`` est
obligatoire : ``pay_page``, ``pay_webhook`` et ``proposal_virement_declare``
sont AllowAny et doivent rester vus par les scanners (cliquet de throttle
YRBAC9). Déplacement pur : corps octet-identiques (seule la profondeur des
imports relatifs locaux change), prouvé par ``tests/golden/split_pv_paiement.json``.
"""
from rest_framework import status
from rest_framework.decorators import (
    api_view, permission_classes, throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from ..models import PaymentLink
from .noyau import (
    PublicLinkRateThrottle, _noindex, _not_found, _refus_apercu_interne,
    _resolve_proposal_link,
)
from .payload_conditions import _acompte_publique


def _company_rib():
    """QX33be — coordonnées de virement (RIB/IBAN) depuis settings/env.

    Non stocké sur un modèle aujourd'hui : lu depuis ``settings.COMPANY_RIB``
    (ou l'env). Vide → aucune instruction de virement affichée (dégradation
    propre, aucun changement de comportement)."""
    from django.conf import settings
    return (getattr(settings, 'COMPANY_RIB', '') or '').strip()


def _deposit_success_payload(devis, token):
    """QX33be — payload d'acompte pour l'écran/email de succès post-signature.

    Montant = 1ʳᵉ tranche de l'échéancier (acompte) calculée sur le TTC REMISÉ
    (chaîne canonique QX1). RIB si configuré. ``card_payment_url`` non nul
    UNIQUEMENT si un vrai PSP est configuré (QXG2) — sinon None. Best-effort :
    jamais d'exception (renvoie un payload minimal)."""
    from decimal import Decimal
    payload = {
        'acompte_ttc': None,
        'pourcentage': None,
        'rib': _company_rib(),
        'message': '',
        'declare_url': f'/api/django/public/proposal/{token}/virement/',
        'card_payment_url': None,
    }
    try:
        from ..deposit import deposit_protection_message
        # PREVIEW-V3 — MÊME helper que la page AVANT signature
        # (`_acompte_publique`) : les deux côtés du parcours ne peuvent plus
        # diverger d'un centime ni d'un pourcent.
        tr = _acompte_publique(devis)
        if tr is not None:
            acompte = Decimal(tr['ttc'])
            payload['acompte_ttc'] = tr['ttc']
            payload['pourcentage'] = tr['pourcentage']
            payload['message'] = deposit_protection_message(
                acompte, reference=devis.reference)
    except Exception:  # noqa: BLE001 — best-effort
        pass
    # QX33be — slot lien carte : actif seulement si un PSP réel est configuré.
    try:
        from django.conf import settings
        provider = (getattr(settings, 'PAYMENT_PROVIDER', '') or '').strip()
        if provider and provider != 'noop':
            payload['card_payment_url'] = (
                f'/api/django/public/proposal/{token}/pay-card/')
    except Exception:  # noqa: BLE001
        pass
    return payload


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PublicLinkRateThrottle])
def proposal_virement_declare(request, token):
    """QX33be — le client déclare « j'ai effectué le virement ».

    Notifie le vendeur (Notification + chatter) et pose un horodatage sur le
    devis via une note chatter — NE change JAMAIS le statut du devis ni ne crée
    de Paiement (l'encaissement réel reste manuel/vérifié, règle #4). Idempotent
    par lien (cache.add). Best-effort : jamais d'exception 500."""
    link = _resolve_proposal_link(token)
    if link is None:
        return _not_found()
    # R4 — déclarer un virement au nom du client poserait une note chatter et
    # enverrait le vendeur vérifier un versement qui n'existe pas.
    if link.via_interne:
        return _refus_apercu_interne()
    devis = link.devis
    # Idempotence : une déclaration par lien et par heure.
    try:
        from django.core.cache import cache
        if not cache.add(f'qx33-virement:{link.pk}', True, 3600):
            return _noindex(Response({
                'detail': 'Votre déclaration a bien été prise en compte.',
                'already': True,
            }))
    except Exception:  # noqa: BLE001
        pass
    # Chatter + notification vendeur (best-effort).
    try:
        from .. import activity
        activity.log_devis_note(
            devis, None,
            'Le client déclare avoir effectué le virement de l\'acompte.')
    except Exception:  # noqa: BLE001
        pass
    try:
        from apps.notifications.services import notify
        from apps.notifications.models import EventType
        vendeur = getattr(devis, 'created_by', None)
        if vendeur is not None:
            notify(
                vendeur, EventType.CLIENT_CONTACT_REQUEST,
                title=f'Virement déclaré — devis {devis.reference}',
                body='Le client indique avoir effectué le virement de '
                     'l\'acompte. À vérifier sur le compte bancaire.',
                link=f'/ventes/devis?devis={devis.id}',
                company=devis.company)
    except Exception:  # noqa: BLE001
        pass
    return _noindex(Response({
        'detail': 'Merci ! Votre déclaration a été transmise à votre '
                  'conseiller.',
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
    Un lien payé renvoie statut='paye' (page de confirmation côté front).

    AUD136 — `montant` était le chiffre FIGÉ à la création du lien : après un
    règlement partiel, la page réclamait au client une somme qu'il ne devait
    plus. Elle affiche désormais `link.montant_a_payer` — le reste dû à
    l'instant T, exactement la valeur à laquelle le webhook borne déjà
    l'encaissement (`record_payment_from_link`). `montant_initial` reste
    exposé comme trace."""
    link = _resolve_payment_link(token, require_valid=False)
    if link is None:
        return _not_found()
    facture = link.facture
    return _noindex(Response({
        'reference': facture.reference,
        'client_name': str(facture.client) if facture.client_id else '',
        'montant': str(link.montant_a_payer),
        'montant_initial': str(link.montant),
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
    from ..services import record_payment_from_link
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
