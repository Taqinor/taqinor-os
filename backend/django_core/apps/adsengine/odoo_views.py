"""ADSENG-ODOO — Endpoint mince du coût-par-signature adossé à Odoo.

``GET /api/django/adsengine/metrics/cost-per-signature-odoo/`` — company-scopé
(jamais une autre société), gaté par ``adsengine_view`` (MÊME patron que
``CostPerSignatureView``/``metrics/cout-par-signature/`` — que ce module ne
touche PAS). Renvoie le nombre Odoo + les composants + les deals signés +
l'attribution par campagne.

READ-ONLY de bout en bout : la vue lit Odoo via le connecteur lecture-seule et ne
mute rien. Sans clés Odoo, la réponse est propre (``configured=False``,
``signatures=0``) — jamais un 500.
"""
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import _user_has_or_legacy

from . import schema_docs as sd


class OdooCostPerSignatureView(APIView):
    """Coût-par-signature calculé contre les VRAIES signatures Odoo."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses=sd.COST_PER_SIGNATURE_ODOO)
    def get(self, request):
        if not _user_has_or_legacy(request.user, 'adsengine_view'):
            return Response({'detail': 'Permission refusée.'}, status=403)
        company = getattr(request.user, 'company', None)
        if company is None:
            return Response({'detail': 'Aucune société.'}, status=400)
        from .odoo_metrics import odoo_cost_per_signature
        return Response(odoo_cost_per_signature(company))
