"""Vues du module « ai_governance » — copilotes IA (Groupe NTAI).

Toutes les vues sont des ``APIView`` de GÉNÉRATION : elles lisent, proposent un
brouillon, et n'écrivent JAMAIS dans un modèle métier. Sans clé LLM/STT
configurée, elles répondent 503 avec un message FR explicite et ne font aucun
appel réseau.
"""
from rest_framework import status
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
