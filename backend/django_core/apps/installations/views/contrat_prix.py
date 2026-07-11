"""Vues FG318 — contrats & accords de prix fournisseur (datés / versionnés).

``ContratPrixFournisseurViewSet`` : CRUD des contrats de prix + cycle de vie
(``activer`` / ``expirer``) + action ``prix-convenu`` qui renvoie le prix
convenu d'un produit à une date (d'après les contrats en vigueur).
``ContratPrixLigneViewSet`` : lignes (SKU + prix négocié). Lecture tout rôle,
écriture responsable/admin. Multi-tenant via ``TenantMixin`` ; les lignes (sans
`company` propre) sont scopées par leur contrat parent. Cross-app :
``stock.Fournisseur`` / ``stock.Produit`` en string-FK. Montants INTERNES.
"""
from datetime import date

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet

from apps.ventes.utils.references import create_with_reference

from ..models import ContratPrixFournisseur, ContratPrixLigne
from ..serializers import (
    ContratPrixFournisseurSerializer, ContratPrixLigneSerializer,
)
from .. import selectors

READ_ACTIONS = ['list', 'retrieve', 'prix_convenu']


class ContratPrixFournisseurViewSet(CompanyScopedModelViewSet):
    """FG318 — contrats de prix fournisseur. Lecture tout rôle, écriture
    responsable/admin. Référence anti-collision + société + `created_by` posés
    serveur ; `fournisseur` validé tenant. Filtrable par `fournisseur`,
    `statut`. Cycle de vie + lookup `prix-convenu`."""
    queryset = ContratPrixFournisseur.objects.select_related(
        'fournisseur', 'created_by').prefetch_related('lignes').all()
    serializer_class = ContratPrixFournisseurSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        fournisseur = params.get('fournisseur')
        if fournisseur:
            qs = qs.filter(fournisseur_id=fournisseur)
        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def _check_tenant(self, serializer):
        company = self.request.user.company
        fournisseur = serializer.validated_data.get('fournisseur')
        if fournisseur is not None and getattr(
                fournisseur, 'company_id', None) != getattr(
                company, 'id', None):
            raise ValidationError(
                {'fournisseur': 'Fournisseur inconnu pour cette société.'})

    def perform_create(self, serializer):
        company = self.request.user.company
        self._check_tenant(serializer)

        def _save(reference):
            return serializer.save(
                company=company, created_by=self.request.user,
                reference=reference)

        create_with_reference(ContratPrixFournisseur, 'CPF', company, _save)

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        serializer.save(company=self.request.user.company)

    @action(detail=True, methods=['post'])
    def activer(self, request, pk=None):
        """FG318 — active le contrat (brouillon → actif)."""
        c = self.get_object()
        c.statut = ContratPrixFournisseur.Statut.ACTIF
        c.save(update_fields=['statut', 'date_modification'])
        return Response(self.get_serializer(c).data)

    @action(detail=True, methods=['post'])
    def expirer(self, request, pk=None):
        """FG318 — expire le contrat (→ expiré)."""
        c = self.get_object()
        c.statut = ContratPrixFournisseur.Statut.EXPIRE
        c.save(update_fields=['statut', 'date_modification'])
        return Response(self.get_serializer(c).data)

    @action(detail=False, methods=['get'], url_path='prix-convenu')
    def prix_convenu(self, request):
        """FG318 — prix convenu d'un produit à une date, d'après les contrats en
        vigueur. Params : `produit` (requis), `fournisseur` (optionnel), `date`
        (optionnelle, YYYY-MM-DD). Lecture seule, montant INTERNE."""
        produit_id = request.query_params.get('produit')
        if not produit_id:
            return Response(
                {'produit': 'Paramètre `produit` requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        a_la_date = None
        raw = request.query_params.get('date')
        if raw:
            try:
                a_la_date = date.fromisoformat(raw)
            except ValueError:
                return Response(
                    {'date': 'Date invalide (attendu YYYY-MM-DD).'},
                    status=status.HTTP_400_BAD_REQUEST)
        result = selectors.prix_convenu_fournisseur(
            request.user.company, produit_id,
            fournisseur_id=request.query_params.get('fournisseur') or None,
            a_la_date=a_la_date)
        return Response(result)


class ContratPrixLigneViewSet(viewsets.ModelViewSet):
    """FG318 — lignes de contrat de prix. La ligne n'a pas de `company` propre :
    le scope société passe par le contrat parent. Filtrable par `contrat`.
    Lecture tout rôle, écriture responsable/admin."""
    queryset = ContratPrixLigne.objects.select_related(
        'contrat', 'produit').all()
    serializer_class = ContratPrixLigneSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.company_id:
            qs = qs.filter(contrat__company=user.company)
        elif not user.is_superuser:
            qs = qs.none()
        contrat = self.request.query_params.get('contrat')
        if contrat:
            qs = qs.filter(contrat_id=contrat)
        return qs

    def _check_parent(self, serializer):
        company = self.request.user.company
        cid = getattr(company, 'id', None)
        contrat = serializer.validated_data.get('contrat')
        if contrat is not None and getattr(contrat, 'company_id', None) != cid:
            raise ValidationError(
                {'contrat': 'Contrat inconnu pour cette société.'})
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
