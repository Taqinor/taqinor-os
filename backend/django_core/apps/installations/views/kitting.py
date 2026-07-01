"""Vues FG328 — pré-assemblage / kitting magasin.

``KitViewSet`` : définition des composites + nomenclature. ``KitComposantViewSet``
: composants (BOM). ``OrdreAssemblageViewSet`` : ordres d'assemblage ; référence
anti-collision posée serveur ; cycle ``demarrer`` / ``terminer`` (la
consommation/production de stock reste pilotée par le module stock). Lecture
tout rôle, écriture responsable/admin. Multi-tenant via ``TenantMixin`` ;
produit/kit validés tenant. Cross-app : ``stock`` en string-FK.
"""
from django.utils import timezone

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import IsAnyRole, IsResponsableOrAdmin

from apps.ventes.utils.references import create_with_reference

from ..models import Kit, KitComposant, OrdreAssemblage
from ..serializers import (
    KitSerializer, KitComposantSerializer, OrdreAssemblageSerializer,
)

READ_ACTIONS = ['list', 'retrieve']


class KitViewSet(TenantMixin, viewsets.ModelViewSet):
    """FG328 — kits de pré-assemblage. Lecture tout rôle, écriture
    responsable/admin. Filtrable par `active`."""
    queryset = Kit.objects.select_related(
        'produit_compose', 'created_by').prefetch_related('composants').all()
    serializer_class = KitSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        active = self.request.query_params.get('active')
        if active in ('0', 'false', 'False'):
            qs = qs.filter(active=False)
        elif active in ('1', 'true', 'True'):
            qs = qs.filter(active=True)
        return qs

    def _check_tenant(self, serializer):
        company = self.request.user.company
        cid = getattr(company, 'id', None)
        produit = serializer.validated_data.get('produit_compose')
        if produit is not None and getattr(
                produit, 'company_id', None) != cid:
            raise ValidationError(
                {'produit_compose': 'Produit inconnu pour cette société.'})

    def perform_create(self, serializer):
        self._check_tenant(serializer)
        serializer.save(
            company=self.request.user.company,
            created_by=self.request.user)

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        serializer.save(company=self.request.user.company)


class KitComposantViewSet(viewsets.ModelViewSet):
    """FG328 — composants de kit. Pas de `company` propre : scope via le kit
    parent. Filtrable par `kit`. Lecture tout rôle, écriture
    responsable/admin."""
    queryset = KitComposant.objects.select_related('kit', 'produit').all()
    serializer_class = KitComposantSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.company_id:
            qs = qs.filter(kit__company=user.company)
        elif not user.is_superuser:
            qs = qs.none()
        kit = self.request.query_params.get('kit')
        if kit:
            qs = qs.filter(kit_id=kit)
        return qs

    def _check_parent(self, serializer):
        company = self.request.user.company
        cid = getattr(company, 'id', None)
        kit = serializer.validated_data.get('kit')
        if kit is not None and getattr(kit, 'company_id', None) != cid:
            raise ValidationError(
                {'kit': 'Kit inconnu pour cette société.'})
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


class OrdreAssemblageViewSet(TenantMixin, viewsets.ModelViewSet):
    """FG328 — ordres d'assemblage. Lecture tout rôle, écriture
    responsable/admin. Référence/société/`created_by` posés serveur. Filtrable
    par `statut`, `kit`."""
    queryset = OrdreAssemblage.objects.select_related(
        'kit', 'created_by').all()
    serializer_class = OrdreAssemblageSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        kit = params.get('kit')
        if kit:
            qs = qs.filter(kit_id=kit)
        return qs

    def _check_tenant(self, serializer):
        company = self.request.user.company
        cid = getattr(company, 'id', None)
        kit = serializer.validated_data.get('kit')
        if kit is not None and getattr(kit, 'company_id', None) != cid:
            raise ValidationError(
                {'kit': 'Kit inconnu pour cette société.'})

    def perform_create(self, serializer):
        company = self.request.user.company
        self._check_tenant(serializer)

        def _save(reference):
            return serializer.save(
                company=company, created_by=self.request.user,
                reference=reference)

        create_with_reference(OrdreAssemblage, 'ASM', company, _save)

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        serializer.save(company=self.request.user.company)

    @action(detail=True, methods=['post'])
    def demarrer(self, request, pk=None):
        """FG328 — passe l'ordre en cours."""
        ordre = self.get_object()
        ordre.statut = OrdreAssemblage.Statut.EN_COURS
        ordre.save(update_fields=['statut', 'date_modification'])
        return Response(self.get_serializer(ordre).data)

    @action(detail=True, methods=['post'])
    def terminer(self, request, pk=None):
        """FG328 — clôture l'ordre (→ terminé, horodate)."""
        ordre = self.get_object()
        ordre.statut = OrdreAssemblage.Statut.TERMINE
        ordre.date_terminaison = timezone.now()
        ordre.save(update_fields=[
            'statut', 'date_terminaison', 'date_modification'])
        return Response(self.get_serializer(ordre).data)
