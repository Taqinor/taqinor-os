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
from ..services import (
    seed_reservations_assemblage, disponibilite_par_ligne,
    alerter_penurie_assemblage,
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
        # XMFG2 — sème les réservations composant depuis la BOM du kit dès la
        # création de l'ordre.
        seed_reservations_assemblage(serializer.instance)

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        serializer.save(company=self.request.user.company)

    @action(detail=True, methods=['get'])
    def disponibilite(self, request, pk=None):
        """XMFG2 — disponibilité par ligne de composant (disponible / partiel
        / manquant, réservation-aware)."""
        ordre = self.get_object()
        return Response(disponibilite_par_ligne(ordre))

    @action(detail=True, methods=['post'])
    def demarrer(self, request, pk=None):
        """FG328/XMFG2 — passe l'ordre en cours. Avertit (non bloquant) si des
        composants manquent."""
        ordre = self.get_object()
        ordre.statut = OrdreAssemblage.Statut.EN_COURS
        ordre.save(update_fields=['statut', 'date_modification'])
        alerter_penurie_assemblage(ordre)
        return Response(self.get_serializer(ordre).data)

    @action(detail=True, methods=['post'])
    def terminer(self, request, pk=None):
        """FG328/XMFG1 — clôture l'ordre (→ terminé, horodate) et backflush le
        stock : consomme les composants du kit, produit le composite. Refuse si
        le kit n'a pas de `produit_compose`. `quantite_produite` (défaut =
        `quantite`) et les emplacements sont éditables au moment de la clôture.
        Idempotent : `stock_mouvemente` empêche une re-clôture de re-mouvementer."""
        from django.db import transaction

        from apps.stock.services import consommer_et_produire_assemblage

        ordre = self.get_object()
        if ordre.kit.produit_compose_id is None:
            raise ValidationError({
                'kit': "Ce kit n'a pas d'article composite "
                       "(produit_compose) : clôture impossible."})

        quantite_produite = request.data.get('quantite_produite')
        try:
            quantite_produite = (
                int(quantite_produite) if quantite_produite not in (None, '')
                else ordre.quantite_produite or ordre.quantite)
        except (TypeError, ValueError):
            raise ValidationError({
                'quantite_produite': 'Quantité produite invalide.'})
        if quantite_produite <= 0:
            raise ValidationError({
                'quantite_produite': 'La quantité produite doit être positive.'})

        emplacement_source_id = request.data.get('emplacement_source')
        emplacement_destination_id = request.data.get('emplacement_destination')

        with transaction.atomic():
            ordre = OrdreAssemblage.objects.select_for_update().get(pk=ordre.pk)
            ordre.quantite_produite = quantite_produite
            if emplacement_source_id:
                ordre.emplacement_source_id = emplacement_source_id
            if emplacement_destination_id:
                ordre.emplacement_destination_id = emplacement_destination_id
            already_moved = ordre.stock_mouvemente
            ordre.statut = OrdreAssemblage.Statut.TERMINE
            ordre.date_terminaison = timezone.now()
            update_fields = [
                'statut', 'date_terminaison', 'date_modification',
                'quantite_produite', 'emplacement_source',
                'emplacement_destination']
            if not already_moved:
                consommer_et_produire_assemblage(
                    company=ordre.company, kit=ordre.kit,
                    composants=ordre.kit.composants.select_related('produit').all(),
                    produit_compose=ordre.kit.produit_compose,
                    quantite_produite=quantite_produite,
                    reference=ordre.reference, user=request.user,
                    emplacement_source=ordre.emplacement_source,
                    emplacement_destination=ordre.emplacement_destination)
                ordre.stock_mouvemente = True
                update_fields.append('stock_mouvemente')
                # XMFG2 — les réservations composant sont désormais consommées
                # (le stock a été décrémenté par le backflush ci-dessus).
                ordre.reservations.filter(
                    active=True, consomme=False).update(consomme=True)
            ordre.save(update_fields=update_fields)
        return Response(self.get_serializer(ordre).data)
