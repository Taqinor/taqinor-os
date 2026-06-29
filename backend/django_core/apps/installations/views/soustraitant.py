"""Vue FG304 — référentiel des sous-traitants chantier.

``SousTraitantViewSet`` : CRUD de l'annuaire des prestataires de main-d'œuvre
sous-traitée (terrassement / génie civil / électricité / levage / transport /
autre), DISTINCT des fournisseurs de matériel. Lecture tout rôle, écriture
responsable/admin. Multi-tenant via ``TenantMixin`` : le queryset est filtré sur
la société de l'utilisateur et la société + ``created_by`` sont posés côté
serveur (jamais lus du corps). Filtrable par ``metier`` et ``actif`` ;
recherche plein-texte sur ``raison_sociale`` et ``ice``."""
from rest_framework import viewsets
from rest_framework.filters import SearchFilter

from authentication.mixins import TenantMixin
from authentication.permissions import IsAnyRole, IsResponsableOrAdmin

from ..models import SousTraitant
from ..serializers import SousTraitantSerializer

READ_ACTIONS = ['list', 'retrieve']


class SousTraitantViewSet(TenantMixin, viewsets.ModelViewSet):
    """FG304 — annuaire des sous-traitants chantier. Lecture tout rôle, écriture
    responsable/admin. Société + `created_by` posés côté serveur. Filtrable par
    `metier` et `actif` ; recherche `?search=` sur la raison sociale et l'ICE."""
    queryset = SousTraitant.objects.select_related('created_by').all()
    serializer_class = SousTraitantSerializer
    filter_backends = [SearchFilter]
    search_fields = ['raison_sociale', 'ice']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        metier = params.get('metier')
        if metier:
            qs = qs.filter(metier=metier)
        actif = params.get('actif')
        if actif is not None and actif != '':
            qs = qs.filter(actif=actif.lower() in ('1', 'true', 'oui', 'yes'))
        return qs

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company, created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(company=self.request.user.company)
