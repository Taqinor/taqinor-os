"""Vues FG329 — planification des livraisons (dépôt → site).

``LivraisonViewSet`` : CRUD des livraisons ; référence anti-collision posée
serveur ; cycle ``expedier`` (→ en transit) / ``livrer`` (→ livrée) / ``annuler``
(→ annulée). ``LivraisonLigneViewSet`` : articles d'une livraison. Lecture tout
rôle, écriture responsable/admin. Multi-tenant via ``TenantMixin`` ;
chantier/dépôt validés tenant. Cross-app : ``stock`` en string-FK.
"""
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import IsAnyRole, IsResponsableOrAdmin

from apps.ventes.utils.references import create_with_reference

from ..models import Livraison, LivraisonLigne
from ..serializers import LivraisonSerializer, LivraisonLigneSerializer

READ_ACTIONS = ['list', 'retrieve']


class LivraisonViewSet(TenantMixin, viewsets.ModelViewSet):
    """FG329 — livraisons planifiées. Lecture tout rôle, écriture
    responsable/admin. Filtrable par `installation`, `statut`, `depot`,
    `date_prevue`."""
    queryset = Livraison.objects.select_related(
        'installation', 'depot', 'created_by').prefetch_related('lignes').all()
    serializer_class = LivraisonSerializer

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
        depot = params.get('depot')
        if depot:
            qs = qs.filter(depot_id=depot)
        date_prevue = params.get('date_prevue')
        if date_prevue:
            qs = qs.filter(date_prevue=date_prevue)
        return qs

    def _check_tenant(self, serializer):
        company = self.request.user.company
        cid = getattr(company, 'id', None)
        for field, label in (
                ('installation', 'Chantier'), ('depot', 'Dépôt'),
                ('transporteur', 'Transporteur')):
            obj = serializer.validated_data.get(field)
            if obj is not None and getattr(obj, 'company_id', None) != cid:
                raise ValidationError(
                    {field: f'{label} inconnu pour cette société.'})

    def perform_create(self, serializer):
        company = self.request.user.company
        self._check_tenant(serializer)

        def _save(reference):
            return serializer.save(
                company=company, created_by=self.request.user,
                reference=reference)

        create_with_reference(Livraison, 'LIV', company, _save)

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        serializer.save(company=self.request.user.company)

    def _set_statut(self, request, statut):
        liv = self.get_object()
        liv.statut = statut
        liv.save(update_fields=['statut', 'date_modification'])
        return Response(self.get_serializer(liv).data)

    @action(detail=True, methods=['post'])
    def expedier(self, request, pk=None):
        """FG329 — passe la livraison en transit."""
        return self._set_statut(request, Livraison.Statut.EN_TRANSIT)

    @action(detail=True, methods=['post'])
    def livrer(self, request, pk=None):
        """FG329 — marque la livraison livrée."""
        return self._set_statut(request, Livraison.Statut.LIVREE)

    @action(detail=True, methods=['post'])
    def annuler(self, request, pk=None):
        """FG329 — annule la livraison."""
        return self._set_statut(request, Livraison.Statut.ANNULEE)


class LivraisonLigneViewSet(viewsets.ModelViewSet):
    """FG329 — lignes de livraison. Pas de `company` propre : scope via la
    livraison parente. Filtrable par `livraison`. Lecture tout rôle, écriture
    responsable/admin."""
    queryset = LivraisonLigne.objects.select_related(
        'livraison', 'produit').all()
    serializer_class = LivraisonLigneSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.company_id:
            qs = qs.filter(livraison__company=user.company)
        elif not user.is_superuser:
            qs = qs.none()
        livraison = self.request.query_params.get('livraison')
        if livraison:
            qs = qs.filter(livraison_id=livraison)
        return qs

    def _check_parent(self, serializer):
        company = self.request.user.company
        cid = getattr(company, 'id', None)
        livraison = serializer.validated_data.get('livraison')
        if livraison is not None and getattr(
                livraison, 'company_id', None) != cid:
            raise ValidationError(
                {'livraison': 'Livraison inconnue pour cette société.'})
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
