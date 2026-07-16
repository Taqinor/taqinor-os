"""Vue FG315 — suivi import / dédouanement.

``DossierImportViewSet`` : CRUD des dossiers d'import (conteneur, incoterm, BL,
dates port, statut douane) + action ``avancer`` qui fait progresser le statut
douanier dans l'ordre canonique (commandé → expédié → arrivé port → en douane →
dédouané → livré). Lecture tout rôle, écriture responsable/admin. Multi-tenant
via ``TenantMixin`` : référence/société/created_by posés côté serveur ;
fournisseur/bon_commande validés tenant. Cross-app : ``stock.Fournisseur`` /
``stock.BonCommandeFournisseur`` en string-FK.
"""
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet

from apps.ventes.utils.references import create_with_reference

from ..models import DossierImport
from ..serializers import DossierImportSerializer
from .. import selectors

READ_ACTIONS = ['list', 'retrieve', 'landed_cost']

# Ordre canonique du statut douanier (jamais alphabétique).
STATUT_ORDER = [
    DossierImport.StatutDouane.COMMANDE,
    DossierImport.StatutDouane.EXPEDIE,
    DossierImport.StatutDouane.ARRIVE_PORT,
    DossierImport.StatutDouane.EN_DOUANE,
    DossierImport.StatutDouane.DEDOUANE,
    DossierImport.StatutDouane.LIVRE,
]


class DossierImportViewSet(CompanyScopedModelViewSet):
    """FG315 — dossiers d'import. Lecture tout rôle, écriture responsable/admin.
    Référence anti-collision + société + `created_by` posés serveur ;
    fournisseur/bon_commande validés tenant. Filtrable par `statut_douane`,
    `fournisseur`. Progression du statut via `avancer`."""
    queryset = DossierImport.objects.select_related(
        'fournisseur', 'bon_commande', 'created_by'
    ).prefetch_related('frais', 'landed_lignes').all()
    serializer_class = DossierImportSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        statut = params.get('statut_douane')
        if statut:
            qs = qs.filter(statut_douane=statut)
        fournisseur = params.get('fournisseur')
        if fournisseur:
            qs = qs.filter(fournisseur_id=fournisseur)
        return qs

    def _check_tenant(self, serializer):
        company = self.request.user.company
        cid = getattr(company, 'id', None)
        for field in ('fournisseur', 'bon_commande'):
            obj = serializer.validated_data.get(field)
            if obj is not None and getattr(obj, 'company_id', None) != cid:
                raise ValidationError(
                    {field: 'Objet inconnu pour cette société.'})

    def perform_create(self, serializer):
        company = self.request.user.company
        self._check_tenant(serializer)

        def _save(reference):
            return serializer.save(
                company=company, created_by=self.request.user,
                reference=reference)

        create_with_reference(DossierImport, 'IMP', company, _save)

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        serializer.save(company=self.request.user.company)

    @action(detail=True, methods=['post'])
    def avancer(self, request, pk=None):
        """FG315 — fait progresser le statut douanier d'un cran dans l'ordre
        canonique. Corps optionnel `statut_douane` pour sauter à un statut
        précis (doit être en aval). Refuse de revenir en arrière."""
        dossier = self.get_object()
        cible = request.data.get('statut_douane')
        try:
            idx = STATUT_ORDER.index(dossier.statut_douane)
        except ValueError:
            idx = 0
        if cible:
            if cible not in STATUT_ORDER:
                return Response(
                    {'statut_douane': 'Statut douanier inconnu.'},
                    status=status.HTTP_400_BAD_REQUEST)
            if STATUT_ORDER.index(cible) < idx:
                return Response(
                    {'statut_douane': 'On ne revient pas en arrière dans le '
                                      'dédouanement.'},
                    status=status.HTTP_400_BAD_REQUEST)
            nouveau = cible
        else:
            nouveau = STATUT_ORDER[min(idx + 1, len(STATUT_ORDER) - 1)]
        dossier.statut_douane = nouveau
        dossier.save(update_fields=['statut_douane', 'date_modification'])
        return Response(self.get_serializer(dossier).data)

    @action(detail=True, methods=['get'], url_path='landed-cost')
    def landed_cost(self, request, pk=None):
        """FG316 — coût de revient débarqué : répartit les frais d'import sur les
        SKU au prorata FOB et renvoie le coût débarqué par ligne. Lecture seule,
        montants INTERNES."""
        dossier = self.get_object()
        return Response(selectors.landed_cost_dossier(dossier))

    @action(detail=True, methods=['post'], url_path='appliquer-cout-stock')
    def appliquer_cout_stock(self, request, pk=None):
        """DC38 — reporte le coût débarqué (FG316) dans le coût d'achat stock :
        écrit la quote-part de frais de chaque SKU dans les frais annexes de la
        ligne du bon de commande d'origine (intégrée au coût moyen pondéré par
        FG67). Écriture responsable/admin. Montants INTERNES."""
        from ..services import appliquer_landed_cost_au_stock
        dossier = self.get_object()
        try:
            resultat = appliquer_landed_cost_au_stock(dossier)
        except ValueError:
            # Message fixe et contrôlé (jamais le texte brut de l'exception —
            # évite toute fuite d'information ; seul ce cas est levé par le
            # service : dossier sans bon de commande).
            return Response(
                {'detail': "Le dossier d'import doit être rattaché à un bon de "
                           "commande fournisseur pour reporter le coût débarqué "
                           "dans le coût d'achat."},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(resultat, status=status.HTTP_200_OK)
