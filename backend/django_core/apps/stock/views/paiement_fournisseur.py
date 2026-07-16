from django.db import transaction  # noqa: F401
from django.db.models import ProtectedError, Count, Min, Max  # noqa: F401
from django.http import HttpResponse  # noqa: F401
from rest_framework import viewsets, filters, status  # noqa: F401
from rest_framework.decorators import action  # noqa: F401
from rest_framework.response import Response  # noqa: F401
from core.viewsets import CompanyScopedModelViewSet
from apps.ventes.utils.references import create_with_reference  # noqa: F401
from ..models import (  # noqa: F401
    Produit, Categorie, Fournisseur, MouvementStock, Marque,
    BonCommandeFournisseur, EmplacementStock, TransfertStock, PrixFournisseur,
    RetourFournisseur, ReceptionFournisseur, FactureFournisseur,
    PaiementFournisseur,
)
from ..serializers import (  # noqa: F401
    ProduitSerializer,
    CategorieSerializer,
    FournisseurSerializer,
    MouvementStockSerializer,
    MarqueSerializer,
    BonCommandeFournisseurSerializer,
    EmplacementStockSerializer,
    TransfertStockSerializer,
    PrixFournisseurSerializer,
    RetourFournisseurSerializer,
    ReceptionFournisseurSerializer,
    FactureFournisseurSerializer,
    PaiementFournisseurSerializer,
)
from authentication.permissions import (  # noqa: F401
    IsAnyRole,
    IsAdminRole,
    IsResponsableOrAdmin,
    HasPermissionOrLegacy,
)

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']

# NOTE: ce module fait partie du découpage de l'ancien views.py monolithe
# (un module par ressource). Comportement et symboles inchangés : le
# package __init__ ré-exporte toutes les vues publiques.


class PaiementFournisseurViewSet(CompanyScopedModelViewSet):
    """G5 — Paiements fournisseur (règlements). Lecture + création/suppression ;
    chaque écriture recalcule le statut de la facture. company posée serveur."""
    queryset = PaiementFournisseur.objects.select_related(
        'facture', 'created_by').all()
    serializer_class = PaiementFournisseurSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_paiement', 'date_creation', 'montant']
    ordering = ['-date_paiement', '-date_creation']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        facture_id = self.request.query_params.get('facture')
        if facture_id:
            qs = qs.filter(facture_id=facture_id)
        return qs

    def create(self, request, *args, **kwargs):
        # XPUR1 — gate paiement : refuse la création si la société a activé
        # le blocage et que le fournisseur a un document de conformité
        # obligatoire manquant/expiré. No-op (comportement historique) quand
        # le paramètre est OFF (défaut).
        facture_id = request.data.get('facture')
        if facture_id:
            try:
                from ..services import (
                    check_paiement_conformite_gate,
                    check_fournisseur_statut_paiement,
                    check_facture_exception_gate,
                )
                facture = FactureFournisseur.objects.select_related(
                    'fournisseur').get(
                    pk=facture_id, company=request.user.company)
                # XPUR4 — fournisseur bloqué paiements (ou total).
                check_fournisseur_statut_paiement(facture.fournisseur)
                check_paiement_conformite_gate(
                    request.user.company, facture.fournisseur)
                # XPUR10 — facture en exception de rapprochement 3 voies
                # (écart hors tolérance société), non encore résolue.
                check_facture_exception_gate(
                    request.user.company, facture)
            except FactureFournisseur.DoesNotExist:
                pass
            except ValueError as exc:
                return Response(
                    {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        self._escompte_flag = None
        response = super().create(request, *args, **kwargs)
        # XPUR6 — informatif (jamais déduit automatiquement) : ce paiement
        # tombe-t-il dans la fenêtre d'escompte du fournisseur ?
        if response.status_code == status.HTTP_201_CREATED and (
                self._escompte_flag is not None):
            response.data['escompte_disponible_pct'] = self._escompte_flag
        return response

    def perform_create(self, serializer):
        from ..services import (
            recompute_facture_fournisseur_statut, compute_ras_tva,
        )
        with transaction.atomic():
            facture = serializer.validated_data['facture']
            montant = serializer.validated_data['montant']
            # XPUR2 — RAS-TVA calculée côté serveur, jamais depuis le corps.
            taux, montant_ras = compute_ras_tva(
                self.request.user.company, facture, montant)
            paiement = serializer.save(
                company=self.request.user.company,
                created_by=self.request.user,
                taux_ras=taux, montant_ras_tva=montant_ras)
            paiement.facture.refresh_from_db()
            recompute_facture_fournisseur_statut(paiement.facture)
            # YLEDG2 — événement documentaire générique (pose du seam pour
            # compta.ecriture_pour_paiement_fournisseur, jamais d'import de
            # son service ici).
            from core.events import paiement_fournisseur_enregistre
            paiement_fournisseur_enregistre.send(
                sender=paiement.__class__, instance=paiement,
                company=self.request.user.company)
            try:
                # XPUR6 — informe (sans jamais déduire automatiquement) si ce
                # paiement tombe dans la fenêtre d'escompte du fournisseur.
                from ..services import escompte_applicable
                fournisseur = facture.fournisseur
                if escompte_applicable(
                        fournisseur, facture.date_facture,
                        paiement.date_paiement):
                    self._escompte_flag = str(fournisseur.escompte_pct)
            except Exception:  # noqa: BLE001 — informatif, jamais bloquant
                pass

    def perform_destroy(self, instance):
        from ..services import recompute_facture_fournisseur_statut
        facture = instance.facture
        with transaction.atomic():
            instance.delete()
            facture.refresh_from_db()
            recompute_facture_fournisseur_statut(facture)

    @action(detail=False, methods=['get'], url_path='ras-tva/export',
            permission_classes=[IsResponsableOrAdmin])
    def export_ras_tva(self, request):
        """XPUR2 — relevé RAS-TVA exportable xlsx pour la télédéclaration
        Simpl-TVA. Filtres optionnels ``?date_debut=`` / ``?date_fin=``
        (YYYY-MM-DD)."""
        from ..services import export_ras_tva_xlsx
        return export_ras_tva_xlsx(
            request.user.company,
            date_debut=request.query_params.get('date_debut'),
            date_fin=request.query_params.get('date_fin'))
