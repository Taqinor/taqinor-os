from django.db import transaction  # noqa: F401
from django.db.models import ProtectedError, Count, Min, Max  # noqa: F401
from django.http import HttpResponse  # noqa: F401
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.parsers import JSONParser
from rest_framework import viewsets, filters, status  # noqa: F401
from rest_framework.decorators import action  # noqa: F401
from rest_framework.response import Response  # noqa: F401
from rest_framework.permissions import BasePermission
from ..openapi_helpers import BINARY, DATE, INT, P, XLSX
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


class PeutLirePaiementsFournisseur(BasePermission):
    """ASTK19 — lecture des règlements fournisseur (survivant unique d'AUD419
    et d'ASTK11) : rôle fin → ``achats_payer`` OU ``prix_achat_voir`` ;
    compte légacy sans rôle fin → responsable/admin ET can_view_buy_prices
    (comportement historique inchangé). Superuser toujours."""

    message = ("Permission « achats_payer » ou « prix_achat_voir » requise "
               "(règlements fournisseur).")

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        if not (user and user.is_authenticated):
            return False
        if user.is_superuser:
            return True
        if getattr(user, 'portee', 'interne') != 'interne':
            return False
        if getattr(user, 'role', None):
            return (user.has_erp_permission('achats_payer')
                    or user.has_erp_permission('prix_achat_voir'))
        return bool(user.is_responsable and user.can_view_buy_prices)


@extend_schema_view(list=extend_schema(parameters=[P('facture', INT, False, 'Facture fournisseur (id)')]))
class PaiementFournisseurViewSet(CompanyScopedModelViewSet):
    """G5 — Paiements fournisseur (règlements). Lecture + création/suppression ;
    chaque écriture recalcule le statut de la facture. company posée serveur."""
    queryset = PaiementFournisseur.objects.select_related(
        'facture', 'created_by').all()
    serializer_class = PaiementFournisseurSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_paiement', 'date_creation', 'montant']
    ordering = ['-date_paiement', '-date_creation']
    # ASTK27 (C-ASTK-004) — un paiement est IMMUABLE par l'API : PUT/PATCH
    # répondent 405. Un PATCH {facture}/{montant} déplaçait ou réduisait un
    # règlement sans recalculer ni le statut des factures ni la RAS-TVA. Une
    # correction passe par l'annulation (DELETE, admin) puis la recréation
    # (POST), qui recalculent tous deux statut et retenue.
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    parser_classes = [JSONParser]

    def get_permissions(self):
        # AUD419 — la LECTURE des règlements fournisseurs n'est plus ouverte à
        # tout rôle interne. `IsAnyRole()` laissait n'importe quel compte
        # authentifié de la société (un magasinier sans la moindre permission
        # financière) lister `montant`/`date_paiement`/`facture` de CHAQUE
        # règlement — soit les rapprochements de trésorerie complets, sans
        # besoin métier démontré.
        #
        # La question « un rôle métier en a-t-il besoin ? » est tranchée par
        # PREUVE plutôt que par supposition : l'unique écran consommateur,
        # `/stock/paiements-fournisseur` (PACT51), déclare déjà
        # `roles: ['responsable','admin']` dans
        # `frontend/src/features/stock/module.config.jsx` — c'est la seule
        # référence à cette ressource dans tout le frontend. Resserrer aligne
        # donc l'API sur son écran ; aucun usage existant ne casse.
        if self.action == 'destroy':
            return [IsAdminRole()]
        if self.action in ('list', 'retrieve'):
            # ASTK19 — survivant unique de la lecture (AUD419 + ASTK11) : un
            # rôle fin lit les règlements s'il porte ``achats_payer`` OU
            # ``prix_achat_voir`` (montants d'achat, D-ASTK-2) ; un compte
            # légacy garde responsable/admin ET can_view_buy_prices.
            return [PeutLirePaiementsFournisseur()]
        if self.action == 'export_ras_tva':
            return [IsResponsableOrAdmin()]
        # ASTK19 (D-ASTK-3) — enregistrer/modifier un règlement = « payer » :
        # ``achats_payer`` (Directeur + Administrateur ; repli légacy).
        return [HasPermissionOrLegacy('achats_payer')()]

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
        from rest_framework.exceptions import ValidationError
        from ..services import (
            recompute_facture_fournisseur_statut, compute_ras_tva,
        )
        with transaction.atomic():
            facture = serializer.validated_data['facture']
            montant = serializer.validated_data['montant']
            # AUD208 (ZACC9) — verrouille la facture ET re-vérifie le solde
            # dû SOUS verrou : la garde de `validate()` (côté serializer)
            # tourne HORS transaction/verrou, avant même que cette vue
            # n'ouvre son `transaction.atomic()` — elle ne protège donc pas
            # contre deux paiements concurrents dont la SOMME dépasse le
            # solde dû (chacun la passe isolément).
            from ..services import (
                verrouiller_facture_fournisseur_et_verifier_solde,
            )
            try:
                facture = verrouiller_facture_fournisseur_et_verifier_solde(
                    facture, montant)
            except ValueError as exc:
                raise ValidationError({'montant': str(exc)})
            # XPUR2 — RAS-TVA calculée côté serveur, jamais depuis le corps.
            taux, montant_ras = compute_ras_tva(
                self.request.user.company, facture, montant)
            paiement = serializer.save(
                company=self.request.user.company,
                facture=facture,
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

    @extend_schema(parameters=[P('date_debut', DATE), P('date_fin', DATE)], responses={XLSX: BINARY})
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
