"""Vues FG314 — commandes-cadres / contrats annuels (blanket orders).

``CommandeCadreViewSet`` : CRUD des contrats-cadres + cycle de vie
(``activer`` / ``cloturer``). ``CommandeCadreLigneViewSet`` : lignes (SKU + prix
négocié + volume engagé). ``AppelCommandeViewSet`` : commandes d'appel
consommant le volume engagé d'une ligne (garde anti-dépassement du volume
restant). Lecture tout rôle, écriture responsable/admin. Multi-tenant via
``TenantMixin`` ; les lignes (sans `company` propre) sont scopées par leur
contrat parent. Cross-app : ``stock.Fournisseur`` / ``stock.Produit`` en
string-FK.
"""
from decimal import Decimal, InvalidOperation

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet

from apps.ventes.utils.references import create_with_reference

from ..models import CommandeCadre, CommandeCadreLigne, AppelCommande
from ..serializers import (
    CommandeCadreSerializer, CommandeCadreLigneSerializer,
    AppelCommandeSerializer,
)

READ_ACTIONS = ['list', 'retrieve']


class CommandeCadreViewSet(CompanyScopedModelViewSet):
    """FG314 — contrats-cadres. Lecture tout rôle, écriture responsable/admin.
    Référence anti-collision + société + `created_by` posés serveur ;
    `fournisseur` validé tenant. Filtrable par `statut`, `fournisseur`. Cycle de
    vie via `activer`/`cloturer`."""
    queryset = CommandeCadre.objects.select_related(
        'fournisseur', 'created_by').prefetch_related('lignes').all()
    serializer_class = CommandeCadreSerializer

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
        fournisseur = params.get('fournisseur')
        if fournisseur:
            qs = qs.filter(fournisseur_id=fournisseur)
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

        create_with_reference(CommandeCadre, 'CC', company, _save)

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        serializer.save(company=self.request.user.company)

    @action(detail=True, methods=['post'])
    def activer(self, request, pk=None):
        """FG314 — active le contrat-cadre (brouillon → actif)."""
        cc = self.get_object()
        cc.statut = CommandeCadre.Statut.ACTIF
        cc.save(update_fields=['statut', 'date_modification'])
        return Response(self.get_serializer(cc).data)

    @action(detail=True, methods=['post'])
    def cloturer(self, request, pk=None):
        """FG314 — clôt le contrat-cadre (→ clos)."""
        cc = self.get_object()
        cc.statut = CommandeCadre.Statut.CLOS
        cc.save(update_fields=['statut', 'date_modification'])
        return Response(self.get_serializer(cc).data)


class CommandeCadreLigneViewSet(viewsets.ModelViewSet):
    """FG314 — lignes de contrat-cadre. La ligne n'a pas de `company` propre :
    le scope société passe par le contrat parent. Filtrable par
    `commande_cadre`. Lecture tout rôle, écriture responsable/admin."""
    queryset = CommandeCadreLigne.objects.select_related(
        'commande_cadre', 'produit').prefetch_related('appels').all()
    serializer_class = CommandeCadreLigneSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.company_id:
            qs = qs.filter(commande_cadre__company=user.company)
        elif not user.is_superuser:
            qs = qs.none()
        cc = self.request.query_params.get('commande_cadre')
        if cc:
            qs = qs.filter(commande_cadre_id=cc)
        return qs

    def _check_parent(self, serializer):
        company = self.request.user.company
        cid = getattr(company, 'id', None)
        cc = serializer.validated_data.get('commande_cadre')
        if cc is not None and getattr(cc, 'company_id', None) != cid:
            raise ValidationError(
                {'commande_cadre': 'Contrat inconnu pour cette société.'})
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


class AppelCommandeViewSet(CompanyScopedModelViewSet):
    """FG314 — commandes d'appel sur une ligne de contrat-cadre. Garde : la
    quantité appelée ne peut pas dépasser le volume engagé restant. Société +
    `created_by` posés serveur ; ligne/chantier validés tenant. Filtrable par
    `ligne`, `chantier`. Lecture tout rôle, écriture responsable/admin."""
    queryset = AppelCommande.objects.select_related(
        'ligne', 'chantier', 'created_by').all()
    serializer_class = AppelCommandeSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        ligne = params.get('ligne')
        if ligne:
            qs = qs.filter(ligne_id=ligne)
        chantier = params.get('chantier')
        if chantier:
            qs = qs.filter(chantier_id=chantier)
        return qs

    def _check_tenant(self, serializer):
        company = self.request.user.company
        cid = getattr(company, 'id', None)
        ligne = serializer.validated_data.get('ligne')
        # La ligne est scopée via son contrat-cadre.
        if ligne is not None and getattr(
                ligne.commande_cadre, 'company_id', None) != cid:
            raise ValidationError(
                {'ligne': 'Ligne inconnue pour cette société.'})
        chantier = serializer.validated_data.get('chantier')
        if chantier is not None and getattr(
                chantier, 'company_id', None) != cid:
            raise ValidationError(
                {'chantier': 'Chantier inconnu pour cette société.'})

    def _check_volume(self, serializer, ligne):
        montant = serializer.validated_data.get('quantite') or Decimal('0')
        try:
            montant = Decimal(str(montant))
        except (InvalidOperation, ValueError):
            montant = Decimal('0')
        if montant > ligne.volume_restant:
            raise ValidationError(
                {'quantite': "L'appel dépasse le volume engagé restant."})

    def perform_create(self, serializer):
        self._check_tenant(serializer)
        ligne = serializer.validated_data.get('ligne')
        if ligne is not None:
            self._check_volume(serializer, ligne)
        serializer.save(
            company=self.request.user.company, created_by=self.request.user)

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        serializer.save(company=self.request.user.company)
