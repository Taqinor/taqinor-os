"""NTADM42 — API publique LECTURE SEULE « statut de licence », sous
/api/public/. Authentifiée par clé d'API (scope ``read:licence``), scopée à
la société de la clé (jamais un paramètre client). Renvoie SEULEMENT
``plan_code``/``modules_inclus``/``sieges_max``/``sieges_utilises`` — aucun
champ interne (prix, historique de changement de plan)."""
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.parametres.models import CompanyProfile
from authentication.services import sieges_utilises

from .auth import ApiKeyAuthentication, ApiKeyRateThrottle, HasApiScope
from .constants import SCOPE_READ_LICENCE
from .public_response import PublicApiResponseMixin


class PublicLicenceStatutView(PublicApiResponseMixin, APIView):
    """``GET /api/public/v1/licence/statut/`` — statut de licence de la
    société porteuse de la clé."""

    authentication_classes = [ApiKeyAuthentication]
    permission_classes = [HasApiScope]
    throttle_classes = [ApiKeyRateThrottle]
    required_scope = SCOPE_READ_LICENCE

    def get(self, request):
        company = request.auth.company
        profile = CompanyProfile.get(company=company)
        plan = profile.plan
        return Response({
            'plan_code': plan.code if plan else None,
            'modules_inclus': list(plan.modules_inclus or []) if plan else [],
            'sieges_max': profile.nb_sieges_max,
            'sieges_utilises': sieges_utilises(company),
        })
