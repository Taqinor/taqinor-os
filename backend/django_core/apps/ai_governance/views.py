"""Vues du module « ai_governance » — copilotes IA (Groupe NTAI).

Toutes les vues sont des ``APIView`` de GÉNÉRATION : elles lisent, proposent un
brouillon, et n'écrivent JAMAIS dans un modèle métier. Sans clé LLM/STT
configurée, elles répondent 503 avec un message FR explicite et ne font aucun
appel réseau.
"""
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from authentication.permissions import IsAnyRole

from .services import AiCopiloteUnavailable


def _unavailable_response(exc: AiCopiloteUnavailable) -> Response:
    """Traduit une :class:`AiCopiloteUnavailable` en 503 (pas de clé) ou 400."""
    code = (status.HTTP_400_BAD_REQUEST if exc.configured
            else status.HTTP_503_SERVICE_UNAVAILABLE)
    return Response({'detail': str(exc)}, status=code)


class DescriptionProduitView(APIView):
    """NTAI13 — ``POST /api/django/ai/description-produit/``.

    Body ``{"produit_id": <int>}``. Renvoie une description commerciale FR + une
    variante courte, à VALIDER par l'utilisateur : rien n'est enregistré ici.
    ``Produit.prix_achat`` n'est jamais transmis au fournisseur (allowlist de
    champs côté service, testée).
    """

    permission_classes = [IsAuthenticated, IsAnyRole]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'ai_copilote'

    def post(self, request):
        from .services import generer_description_produit

        produit_id = request.data.get('produit_id')
        if produit_id in (None, ''):
            return Response({'detail': 'produit_id est requis.'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            resultat = generer_description_produit(
                company=request.user.company, produit_id=produit_id)
        except AiCopiloteUnavailable as exc:
            return _unavailable_response(exc)
        return Response(resultat)


class RedigerView(APIView):
    """NTAI11 — ``POST /api/django/ai/rediger/``.

    Body ``{"content_type": "crm.lead", "object_id": 12, "canal":
    "email|whatsapp|sms", "intention": "..."}``. Aplatit le fil (chatter +
    activités) de la fiche et renvoie un brouillon FR ÉDITABLE.

    N'ENVOIE JAMAIS : la réponse porte ``envoye: false`` ; l'envoi reste une
    action utilisateur explicite via les endpoints d'envoi existants. La
    relance CRM et la réponse SAV réutilisent CET endpoint.
    """

    permission_classes = [IsAuthenticated, IsAnyRole]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'ai_copilote'

    def post(self, request):
        from .services import rediger_brouillon

        content_type = request.data.get('content_type')
        object_id = request.data.get('object_id')
        if not content_type or object_id in (None, ''):
            return Response(
                {'detail': 'content_type et object_id sont requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            resultat = rediger_brouillon(
                company=request.user.company,
                content_type=content_type,
                object_id=object_id,
                canal=request.data.get('canal') or 'email',
                intention=request.data.get('intention') or '')
        except AiCopiloteUnavailable as exc:
            return _unavailable_response(exc)
        return Response(resultat)


class CrInterventionView(APIView):
    """NTAI12 — ``POST /api/django/ai/cr-intervention/`` (multipart).

    Champs : ``file`` (mémo vocal) et ``ticket_id`` optionnel. Transcrit puis
    structure le mémo en ``{diagnostic, travaux, pieces, recommandations}``
    pour PRÉ-REMPLIR le rapport du ticket SAV.

    Ne change JAMAIS le statut du ticket (le moteur SAV existant reste seul
    maître des transitions) et ne persiste JAMAIS l'audio reçu.
    """

    permission_classes = [IsAuthenticated, IsAnyRole]
    parser_classes = [MultiPartParser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'ai_transcription'

    def post(self, request):
        from .services import cr_intervention_depuis_audio

        upload = request.FILES.get('file')
        if not upload:
            return Response({'detail': 'Aucun fichier audio fourni.'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            content = upload.read()
        finally:
            upload.close()

        try:
            resultat = cr_intervention_depuis_audio(
                company=request.user.company, file_bytes=content,
                ticket_id=request.data.get('ticket_id'))
        except AiCopiloteUnavailable as exc:
            return _unavailable_response(exc)
        return Response(resultat)


class RapportPeriodeView(APIView):
    """NTAI36 — ``POST /api/django/ai/rapport-periode/``.

    Body ``{"module": "commercial|facturation", "periode": "AAAA-MM"}``.

    Les CHIFFRES sont calculés par le serveur via les sélecteurs de lecture
    existants ; le LLM ne fait que les mettre en phrases. Un narratif
    contenant un nombre absent des métriques est REFUSÉ (400), jamais rendu.
    Brouillon éditable — ``envoye: false``, aucune diffusion automatique.
    """

    permission_classes = [IsAuthenticated, IsAnyRole]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'ai_copilote'

    def post(self, request):
        from .services import rapport_periode

        try:
            resultat = rapport_periode(
                company=request.user.company,
                module=request.data.get('module') or '',
                periode=request.data.get('periode') or '')
        except AiCopiloteUnavailable as exc:
            return _unavailable_response(exc)
        return Response(resultat)
