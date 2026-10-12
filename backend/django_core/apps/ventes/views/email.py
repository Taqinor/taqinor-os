from drf_spectacular.utils import extend_schema
from .. import openapi_shapes as SH
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from authentication.permissions import IsAnyRole
import logging

logger = logging.getLogger(__name__)

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']


# NOTE: ce module fait partie du découpage de l'ancien views.py monolithe
# (un module par ressource). Comportement et symboles inchangés : le
# package __init__ ré-exporte toutes les vues publiques.


@extend_schema(responses=SH.EmailConfigResponse)
@api_view(['GET'])
@permission_classes([IsAnyRole])
def email_config(request):
    """N87 — État du compte d'envoi email (lecture seule, informatif).

    Renvoie si un compte d'envoi (Brevo/SMTP) est réellement configuré et
    l'adresse expéditrice. Quand `configured` est False, l'envoi reste un NO-OP
    (backend console) — le comportement actuel est préservé. La configuration
    réelle (clé Brevo, expéditeur) se fait par variables d'environnement, pas
    via cet endpoint."""
    from django.conf import settings as dj_settings
    from ..email_service import is_email_configured
    return Response({
        'configured': is_email_configured(),
        'from_email': getattr(dj_settings, 'DEFAULT_FROM_EMAIL', ''),
        'inbound_configured': _inbound_configured(),
    })


def _inbound_configured():
    try:
        from ..inbound_email import is_inbound_configured
        return is_inbound_configured()
    except Exception:
        logger.warning("email._inbound_configured : erreur ignorée (mode dégradé)", exc_info=True)
        return False
