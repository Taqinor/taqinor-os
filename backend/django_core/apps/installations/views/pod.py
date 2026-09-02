"""Vues FG330 — preuve de livraison (POD).

``PreuveLivraisonViewSet`` : CRUD de la preuve rattachée à une livraison ;
société/`created_by` posés serveur ; ``horodatage`` posé serveur s'il est absent.
Lecture tout rôle, écriture responsable/admin. Multi-tenant via ``TenantMixin`` ;
la livraison référencée est validée tenant. Cross-app : ``records.Attachment``
(foundation) en string-FK.
"""
from django.utils import timezone

from rest_framework.exceptions import ValidationError

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet
from apps.core.destroy_mixins import UsageGuardedDestroyMixin

from ..models import PreuveLivraison
from ..serializers import PreuveLivraisonSerializer

READ_ACTIONS = ['list', 'retrieve']


class PreuveLivraisonViewSet(UsageGuardedDestroyMixin,
                             CompanyScopedModelViewSet):
    """FG330 — preuves de livraison. Lecture tout rôle, écriture
    responsable/admin. Filtrable par `livraison`.

    AUD302 — le ``destroy`` nu de DRF laissait détruire définitivement une
    preuve de livraison SIGNÉE (signature du client + horodatage capturés),
    sans une seule ligne au Journal. Le mixin apporte la garde 409 en français
    et la trace ``AuditLog`` de toute suppression restant autorisée (ce modèle
    n'est pas dans ``TRACKED_MODELS`` — le mixin est le SEUL endroit qui la
    pose)."""
    queryset = PreuveLivraison.objects.select_related(
        'livraison', 'photo', 'created_by').all()
    serializer_class = PreuveLivraisonSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def destroy_guard_message(self, preuve):
        signee = bool((preuve.signature_data or '').strip()
                      or (preuve.signataire_nom or '').strip())
        if signee and preuve.horodatage is not None:
            return ("Cette preuve de livraison est signée et horodatée : "
                    "elle atteste la remise au client et ne peut plus être "
                    "supprimée.")
        return None

    def get_queryset(self):
        qs = super().get_queryset()
        livraison = self.request.query_params.get('livraison')
        if livraison:
            qs = qs.filter(livraison_id=livraison)
        return qs

    def _check_tenant(self, serializer):
        company = self.request.user.company
        cid = getattr(company, 'id', None)
        livraison = serializer.validated_data.get('livraison')
        if livraison is not None and getattr(
                livraison, 'company_id', None) != cid:
            raise ValidationError(
                {'livraison': 'Livraison inconnue pour cette société.'})

    def perform_create(self, serializer):
        self._check_tenant(serializer)
        horodatage = serializer.validated_data.get('horodatage')
        serializer.save(
            company=self.request.user.company,
            created_by=self.request.user,
            horodatage=horodatage or timezone.now())

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        serializer.save(company=self.request.user.company)
