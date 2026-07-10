"""Vues FG323 — suivi du stock par numéro de série en entrepôt.

``SerieEntrepotViewSet`` : CRUD du registre série→emplacement→casier ; société/
`created_by` posés serveur ; cycle ``reserver`` (→ réservé, lie un chantier) /
``sortir`` (→ sorti). Lecture tout rôle, écriture responsable/admin. Multi-tenant
via ``TenantMixin`` ; produit/emplacement/casier/chantier validés tenant.
Cross-app : ``stock`` en string-FK.
"""
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet

from ..models import SerieEntrepot, Installation
from ..serializers import SerieEntrepotSerializer

READ_ACTIONS = ['list', 'retrieve']


class SerieEntrepotViewSet(CompanyScopedModelViewSet):
    """FG323 — n° de série en entrepôt. Lecture tout rôle, écriture
    responsable/admin. Filtrable par `produit`, `statut`, `numero_serie`,
    `bin`, `emplacement`."""
    queryset = SerieEntrepot.objects.select_related(
        'produit', 'emplacement', 'bin', 'installation', 'created_by').all()
    serializer_class = SerieEntrepotSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        for field in ('produit', 'statut', 'bin', 'emplacement'):
            val = params.get(field)
            if val:
                qs = qs.filter(**{f'{field}_id' if field in (
                    'produit', 'bin', 'emplacement') else field: val})
        numero = params.get('numero_serie')
        if numero:
            qs = qs.filter(numero_serie__icontains=numero)
        return qs

    def _check_tenant(self, serializer):
        company = self.request.user.company
        cid = getattr(company, 'id', None)
        for field, label in (
                ('produit', 'Produit'), ('emplacement', 'Emplacement'),
                ('bin', 'Casier'), ('installation', 'Chantier')):
            obj = serializer.validated_data.get(field)
            if obj is not None and getattr(obj, 'company_id', None) != cid:
                raise ValidationError(
                    {field: f'{label} inconnu pour cette société.'})

    def _check_unique_serial(self, serializer, instance=None):
        """Garde l'unicité (société, produit, n° série) côté API → 400 propre
        plutôt qu'une IntegrityError 500 au contact de la contrainte DB."""
        produit = serializer.validated_data.get(
            'produit', getattr(instance, 'produit', None))
        numero = serializer.validated_data.get(
            'numero_serie', getattr(instance, 'numero_serie', None))
        if produit is None or not numero:
            return
        qs = SerieEntrepot.objects.filter(
            company=self.request.user.company,
            produit=produit, numero_serie=numero)
        if instance is not None:
            qs = qs.exclude(pk=instance.pk)
        if qs.exists():
            raise ValidationError(
                {'numero_serie':
                    'Ce numéro de série existe déjà pour ce produit.'})

    def perform_create(self, serializer):
        self._check_tenant(serializer)
        self._check_unique_serial(serializer)
        serializer.save(
            company=self.request.user.company,
            created_by=self.request.user)

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        self._check_unique_serial(serializer, instance=serializer.instance)
        serializer.save(company=self.request.user.company)

    @action(detail=True, methods=['post'])
    def reserver(self, request, pk=None):
        """FG323 — réserve la pièce pour un chantier (→ réservé). Body optionnel
        `installation` (validé tenant)."""
        serie = self.get_object()
        company = request.user.company
        inst_id = request.data.get('installation')
        if inst_id:
            inst = Installation.objects.filter(
                company=company, id=inst_id).first()
            if inst is None:
                return Response(
                    {'installation': 'Chantier inconnu pour cette société.'},
                    status=status.HTTP_400_BAD_REQUEST)
            serie.installation = inst
        serie.statut = SerieEntrepot.Statut.RESERVE
        serie.save(update_fields=[
            'statut', 'installation', 'date_modification'])
        return Response(self.get_serializer(serie).data)

    @action(detail=True, methods=['post'])
    def sortir(self, request, pk=None):
        """FG323 — sort la pièce de l'entrepôt (→ sorti)."""
        serie = self.get_object()
        serie.statut = SerieEntrepot.Statut.SORTI
        serie.save(update_fields=['statut', 'date_modification'])
        return Response(self.get_serializer(serie).data)
