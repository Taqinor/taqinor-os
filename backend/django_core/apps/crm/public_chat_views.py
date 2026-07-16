"""XMKT37 — Livechat / assistant IA de qualification, côté ERP uniquement.

Endpoints PUBLICS (sans login) pour un visiteur ANONYME du site public :
ouvrir une session, poster un message, lire les réponses (polling — pas de
WebSocket, même choix fondateur que la messagerie interne). Même modèle de
confiance que ``webhooks/website-leads/`` : la société est résolue CÔTÉ
SERVEUR (settings ``META_LEAD_ADS_COMPANY_ID``-like : réutilise
``WEBSITE_LEADS_COMPANY_ID``), jamais reçue du corps de requête. Le token de
session identifie UNIQUEMENT la session (imprévisible, comme ``ShareLink``).

Réponse IA : ``core.ai`` (providers/registry, pattern NoOp) — le prompt de
qualification n'expose JAMAIS de donnée interne (prix_achat/marges exclus par
construction : ce module n'importe aucun modèle produit/prix). Sans clé LLM,
mode dégradé « capture seule » : message d'absence configurable + le visiteur
laisse ses coordonnées pour un rappel — jamais d'exception.
"""
import logging

from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import (
    api_view, permission_classes, throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from authentication.models import Company

from .models import ChatSessionPublique

logger = logging.getLogger(__name__)

#: Message d'absence par défaut affiché en mode dégradé (sans clé LLM).
DEFAULT_AWAY_MESSAGE = (
    "Merci pour votre message ! Notre assistant automatique n'est pas "
    "disponible pour le moment. Laissez-nous votre nom et un téléphone ou "
    "email, un commercial TAQINOR vous recontactera rapidement."
)


class PublicChatRateThrottle(SimpleRateThrottle):
    """Débit limité par IP + jeton de session (cache-based, pas de dépendance
    externe) — décourage l'abus sans jamais bloquer un visiteur légitime."""

    scope = 'public_livechat'
    rate = '30/minute'

    def get_rate(self):
        return self.rate

    def get_cache_key(self, request, view):
        token = (view.kwargs or {}).get('token', '') if view else ''
        ident = self.get_ident(request)
        return self.cache_format % {
            'scope': self.scope,
            'ident': f'{ident}:{token}',
        }


def _resolve_company():
    """Même résolution serveur que le webhook site (WEBSITE_LEADS_COMPANY_ID,
    sinon la première Company) — jamais un id venu du corps de requête.

    QXG5 (code guard) : ``WEBSITE_LEADS_COMPANY_ID`` DOIT être posé en prod dès
    qu'une 2e ``Company`` existe (founder ops check, gated) ; sans elle le
    repli sur la 1re Company par pk est ARBITRAIRE et peut router
    silencieusement une session livechat vers le mauvais tenant. On ne casse
    jamais l'endpoint public (le repli reste "safe"), mais on lève un
    ``logger.error`` LOUD dès que la config est ambiguë, pour rendre un défaut
    de configuration prod visible plutôt que silencieux."""
    company_id = getattr(settings, 'WEBSITE_LEADS_COMPANY_ID', None)
    if company_id:
        company = Company.objects.filter(pk=company_id).first()
        if company is None:
            logger.error(
                "_resolve_company: WEBSITE_LEADS_COMPANY_ID=%r ne correspond "
                "à aucune Company — vérifier la configuration prod.",
                company_id,
            )
        return company
    total = Company.objects.count()
    fallback = Company.objects.order_by('pk').first()
    if total > 1:
        logger.error(
            "_resolve_company: WEBSITE_LEADS_COMPANY_ID n'est pas configuré "
            "et %d Company existent — repli ARBITRAIRE sur la 1re (pk=%s). "
            "Risque de routage silencieux vers le mauvais tenant : poser "
            "WEBSITE_LEADS_COMPANY_ID en prod (QXG5).",
            total, getattr(fallback, 'pk', None),
        )
    return fallback


def _append_transcript(session, auteur, texte):
    entry = {
        'auteur': auteur,
        'texte': texte,
        'date': timezone.now().isoformat(),
    }
    session.transcript = list(session.transcript or []) + [entry]
    session.save(update_fields=['transcript', 'last_message_at'])
    return entry


@api_view(['POST'])
@permission_classes([AllowAny])
def open_chat_session(request):
    """Ouvre une nouvelle session livechat pour un visiteur anonyme."""
    company = _resolve_company()
    if company is None:
        return Response(
            {'detail': 'Service indisponible.'},
            status=status.HTTP_404_NOT_FOUND)
    session = ChatSessionPublique.objects.create(company=company)
    return Response(
        {'token': session.token, 'statut': session.statut},
        status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PublicChatRateThrottle])
def post_chat_message(request, token):
    """Poste un message VISITEUR dans une session ; renvoie la réponse
    (assistant IA si configuré, sinon message d'absence en mode dégradé).

    Jeton invalide → 404 amical (aucune fuite). Dès que nom + contact
    (téléphone/email) sont capturés dans le fil, un Lead est créé (canal
    livechat) et le transcript y est collé en note chatter — la session
    passe alors ``qualifiee``.
    """
    session = ChatSessionPublique.objects.filter(token=token).first()
    if session is None:
        return Response(
            {'detail': 'Session introuvable.'},
            status=status.HTTP_404_NOT_FOUND)
    if session.statut == ChatSessionPublique.Statut.FERMEE:
        return Response(
            {'detail': 'Cette session est fermée.'},
            status=status.HTTP_410_GONE)

    texte = str(request.data.get('message', '')).strip()
    if not texte:
        return Response(
            {'detail': 'Message vide.'}, status=status.HTTP_400_BAD_REQUEST)
    texte = texte[:4000]  # borne défensive — pas de charge illimitée en base.

    _append_transcript(session, 'visiteur', texte)

    from core.ai.services import (
        extract_livechat_qualification, qualify_livechat_reply,
    )

    reply_draft = qualify_livechat_reply(session.transcript)
    if reply_draft.available:
        reply_text = reply_draft.draft
    else:
        reply_text = DEFAULT_AWAY_MESSAGE
    _append_transcript(session, 'assistant', reply_text)

    extracted = extract_livechat_qualification(session.transcript)
    lead_created = False
    if extracted.has_contact and session.lead_id is None:
        from .services import create_lead_from_livechat
        transcript_text = '\n'.join(
            f"[{e.get('auteur')}] {e.get('texte')}"
            for e in (session.transcript or [])
        )
        lead = create_lead_from_livechat(
            company=session.company,
            nom=extracted.nom or 'Prospect livechat',
            telephone=extracted.telephone,
            email=extracted.email,
            transcript_text=transcript_text,
        )
        session.lead = lead
        session.statut = ChatSessionPublique.Statut.QUALIFIEE
        session.save(update_fields=['lead', 'statut'])
        lead_created = True

    return Response({
        'reply': reply_text,
        'statut': session.statut,
        'lead_created': lead_created,
    })


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([PublicChatRateThrottle])
def get_chat_session(request, token):
    """Lit le transcript d'une session (polling — pas de WebSocket)."""
    session = ChatSessionPublique.objects.filter(token=token).first()
    if session is None:
        return Response(
            {'detail': 'Session introuvable.'},
            status=status.HTTP_404_NOT_FOUND)
    return Response({
        'transcript': session.transcript,
        'statut': session.statut,
    })
