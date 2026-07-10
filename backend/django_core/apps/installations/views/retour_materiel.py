"""Vues YSTCK4 — retour chantier (matériel non posé rapporté au dépôt).

``RetourMaterielViewSet`` : CRUD des retours + action ``valider`` qui poste
les mouvements ENTREE (plafonnés à la quantité réellement sortie pour ce
chantier). ``RetourMaterielLigneViewSet`` : lignes {produit, quantité}.
Lecture tout rôle, écriture responsable/admin. Multi-tenant via
``TenantMixin`` ; société posée côté serveur, jamais lue du corps."""
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework import status

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet

from ..models import RetourMateriel, RetourMaterielLigne
from ..serializers import (
    RetourMaterielSerializer, RetourMaterielLigneSerializer,
)
from ..services import valider_retour_materiel

READ_ACTIONS = ['list', 'retrieve']


class RetourMaterielViewSet(CompanyScopedModelViewSet):
    """YSTCK4 — retours de matériel non posé, d'un chantier vers le dépôt.
    Lecture tout rôle, écriture responsable/admin. Filtrable par
    `installation`, `statut`."""
    queryset = RetourMateriel.objects.select_related(
        'installation', 'created_by').prefetch_related('lignes').all()
    serializer_class = RetourMaterielSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        installation = params.get('installation')
        if installation:
            qs = qs.filter(installation_id=installation)
        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def _check_tenant(self, serializer):
        company = self.request.user.company
        cid = getattr(company, 'id', None)
        installation = serializer.validated_data.get('installation')
        if installation is not None and installation.company_id != cid:
            raise ValidationError(
                {'installation': 'Chantier inconnu pour cette société.'})

    def perform_create(self, serializer):
        self._check_tenant(serializer)
        serializer.save(
            company=self.request.user.company,
            created_by=self.request.user)

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        serializer.save(company=self.request.user.company)

    @action(detail=True, methods=['post'])
    def valider(self, request, pk=None):
        """YSTCK4 — valide le retour : poste les mouvements ENTREE (plafonnés
        à la quantité réellement sortie pour ce chantier). Refuse (400) si une
        ligne dépasse le retournable."""
        retour = self.get_object()
        try:
            valider_retour_materiel(retour, request.user)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        retour.refresh_from_db()
        return Response(self.get_serializer(retour).data)


class RetourMaterielLigneViewSet(viewsets.ModelViewSet):
    """YSTCK4 — lignes d'un retour de matériel. Pas de `company` propre :
    scope via le retour parent. Filtrable par `retour`."""
    queryset = RetourMaterielLigne.objects.select_related(
        'retour', 'produit').all()
    serializer_class = RetourMaterielLigneSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.company_id:
            qs = qs.filter(retour__installation__company=user.company)
        elif not user.is_superuser:
            qs = qs.none()
        retour = self.request.query_params.get('retour')
        if retour:
            qs = qs.filter(retour_id=retour)
        return qs

    def _check_parent(self, serializer):
        company = self.request.user.company
        cid = getattr(company, 'id', None)
        retour = serializer.validated_data.get('retour')
        if retour is not None and retour.installation.company_id != cid:
            raise ValidationError(
                {'retour': 'Retour inconnu pour cette société.'})
        produit = serializer.validated_data.get('produit')
        if produit is not None and getattr(
                produit, 'company_id', None) != cid:
            raise ValidationError(
                {'produit': 'Produit inconnu pour cette société.'})

    def perform_create(self, serializer):
        self._check_parent(serializer)
        serializer.save()

    def perform_update(self, serializer):
        self._check_parent(serializer)
        serializer.save()
