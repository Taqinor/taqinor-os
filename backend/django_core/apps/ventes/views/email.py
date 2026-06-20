from django.db import transaction  # noqa: F401
from django.http import HttpResponse  # noqa: F401
from django.utils import timezone  # noqa: F401
from rest_framework import viewsets, status, filters  # noqa: F401
from rest_framework.decorators import action, api_view, permission_classes  # noqa: F401
from rest_framework.response import Response  # noqa: F401
from apps.stock.services import (  # noqa: F401
    mouvement_type_sortie, record_stock_movement,
)
from ..models import (  # noqa: F401
    Devis, LigneDevis, BonCommande, Facture, LigneFacture, Paiement,
    Avoir, LigneAvoir, FollowupLevel, RelanceLog, EmailLog,
)
from ..serializers import (  # noqa: F401
    DevisSerializer,
    DevisWriteSerializer,
    BonCommandeSerializer,
    LigneDevisSerializer,
    FactureSerializer,
    FactureWriteSerializer,
    LigneFactureSerializer,
    PaiementSerializer,
    AvoirSerializer,
    RelanceLogSerializer,
    DevisActivitySerializer,
)
from authentication.permissions import (  # noqa: F401
    IsAnyRole,
    IsResponsableOrAdmin,
    IsAdminRole,
)
from ..utils.references import create_with_reference  # noqa: F401
from ..utils.company_settings import create_numbered  # noqa: F401

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']


from authentication.scoping import scope_queryset  # noqa: E402,F401


def _company_qs(qs, user):
    """Filter queryset to user's company. Superusers without company see all."""
    if user.company_id:
        return qs.filter(company=user.company)
    if user.is_superuser:
        return qs
    return qs.none()

# NOTE: ce module fait partie du découpage de l'ancien views.py monolithe
# (un module par ressource). Comportement et symboles inchangés : le
# package __init__ ré-exporte toutes les vues publiques.


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
        return False
