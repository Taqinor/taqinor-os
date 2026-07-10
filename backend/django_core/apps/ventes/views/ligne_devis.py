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


class LigneDevisViewSet(CompanyScopedModelViewSet):
    # ARC5 — sweep TenantMixin : base transverse unique. LigneDevis N'A PAS de
    # champ `company` (elle est scopée via son parent `devis__company`), donc la
    # base TenantMixin ne convient PAS telle quelle : son get_queryset
    # (`qs.filter(company=…)`) lèverait un FieldError, et son perform_create
    # (`save(company=…)`) écrirait un champ inexistant. On SURCHARGE donc
    # INTÉGRALEMENT get_queryset (scoping via devis__company, en partant du
    # queryset ModelViewSet non filtré — PAS de super() TenantMixin) ainsi que
    # perform_create/perform_update. Comportement et matrice 401/403/404 (404
    # cross-tenant) STRICTEMENT inchangés ; l'héritage sert la classification au
    # socle (règle #4 : aucun statut/sérialisation touché).
    queryset = LigneDevis.objects.select_related('devis', 'produit').all()
    serializer_class = LigneDevisSerializer

    def get_queryset(self):
        # NE PAS passer par super() (TenantMixin filtrerait sur un champ
        # `company` absent de LigneDevis) : on part du queryset ModelViewSet brut.
        qs = viewsets.ModelViewSet.get_queryset(self)
        user = self.request.user
        if user.company_id:
            return qs.filter(devis__company=user.company)
        if user.is_superuser:
            return qs
        return qs.none()

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS + ['destroy']:
            # Retirer une LIGNE fait partie de l'édition normale d'un
            # brouillon (le générateur remplace les lignes) — même niveau
            # que les autres écritures. Supprimer le DEVIS entier reste admin.
            return [IsResponsableOrAdmin()]
        return [IsAdminRole()]

    def _check_tenant(self, serializer):
        """ERR7 — le devis ciblé par la ligne doit appartenir à la société de
        l'utilisateur (refuse l'injection IDOR d'une ligne sur le document d'un
        autre tenant). Superuser sans société : non borné."""
        from rest_framework.exceptions import ValidationError
        user = self.request.user
        devis = serializer.validated_data.get('devis')
        if devis is not None and user.company_id \
                and devis.company_id != user.company_id:
            raise ValidationError({'devis': 'Devis inconnu.'})

    def _check_devis_not_frozen(self, devis):
        """YDOCF2 — les lignes d'un devis figé (accepté/refusé/expiré) ne sont
        plus librement éditables : le BC/Facture/BoM chantier aval sont déjà
        générés depuis le contenu figé. `reviser` (clone en V+1) reste la
        voie de modification."""
        from rest_framework.exceptions import ValidationError
        FROZEN = {Devis.Statut.ACCEPTE, Devis.Statut.REFUSE, Devis.Statut.EXPIRE}
        if devis is not None and devis.statut in FROZEN:
            raise ValidationError({
                'devis': 'Devis figé — révisez-le (reviser) pour le modifier.'})

    def perform_create(self, serializer):
        self._check_tenant(serializer)
        self._check_devis_not_frozen(serializer.validated_data.get('devis'))
        serializer.save()

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        self._check_devis_not_frozen(serializer.instance.devis)
        serializer.save()

    def perform_destroy(self, instance):
        self._check_devis_not_frozen(instance.devis)
        instance.delete()
