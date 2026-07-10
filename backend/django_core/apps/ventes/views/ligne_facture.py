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
from core.viewsets import CompanyScopedModelViewSet  # noqa: F401  ARC5
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


class LigneFactureViewSet(CompanyScopedModelViewSet):
    # ARC5 — sweep TenantMixin : base transverse unique. LigneFacture N'A PAS de
    # champ `company` (elle est scopée via son parent `facture__company`), donc la
    # base TenantMixin ne convient PAS telle quelle : son get_queryset
    # (`qs.filter(company=…)`) lèverait un FieldError, et son perform_create
    # (`save(company=…)`) écrirait un champ inexistant. On SURCHARGE donc
    # INTÉGRALEMENT get_queryset (scoping via facture__company, en partant du
    # queryset ModelViewSet non filtré — PAS de super() TenantMixin) ainsi que
    # perform_create/perform_update. Comportement et matrice 401/403/404 (404
    # cross-tenant) STRICTEMENT inchangés (règle #4 : aucun statut/sérialisation
    # Facture touché).
    queryset = LigneFacture.objects.select_related(
        'facture', 'produit'
    ).all()
    serializer_class = LigneFactureSerializer

    def get_queryset(self):
        # NE PAS passer par super() (TenantMixin filtrerait sur un champ
        # `company` absent de LigneFacture) : on part du queryset ModelViewSet brut.
        qs = viewsets.ModelViewSet.get_queryset(self)
        user = self.request.user
        if user.company_id:
            return qs.filter(facture__company=user.company)
        if user.is_superuser:
            return qs
        return qs.none()

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS:
            return [IsResponsableOrAdmin()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        return [IsAdminRole()]

    def _check_tenant(self, serializer):
        """ERR7 — la facture ciblée par la ligne doit appartenir à la société de
        l'utilisateur (refuse l'injection IDOR d'une ligne sur le document d'un
        autre tenant). Superuser sans société : non borné."""
        from rest_framework.exceptions import ValidationError
        user = self.request.user
        facture = serializer.validated_data.get('facture')
        if facture is not None and user.company_id \
                and facture.company_id != user.company_id:
            raise ValidationError({'facture': 'Facture inconnue.'})

    def _check_immuable(self, facture):
        """XFAC24 — une ligne d'une facture émise IMMUABLE ne peut plus être
        créée/modifiée/supprimée (correction par avoir + nouvelle facture).
        Flag OFF (défaut) ou facture brouillon → comportement inchangé."""
        if facture is None or facture.statut == facture.Statut.BROUILLON:
            return
        from apps.parametres.models import CompanyProfile
        from rest_framework.exceptions import ValidationError
        profile = CompanyProfile.get(company=facture.company)
        if getattr(profile, 'factures_immuables', False):
            raise ValidationError({
                'detail': (
                    "Facture immuable : impossible de modifier les lignes "
                    "d'une facture émise. Corrigez par un avoir puis une "
                    "nouvelle facture."
                ),
            })

    def perform_create(self, serializer):
        self._check_tenant(serializer)
        self._check_immuable(serializer.validated_data.get('facture'))
        serializer.save()

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        self._check_immuable(serializer.instance.facture)
        serializer.save()

    def perform_destroy(self, instance):
        self._check_immuable(instance.facture)
        instance.delete()
