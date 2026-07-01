from django.db import transaction  # noqa: F401
from django.db.models import ProtectedError, Count, Min, Max  # noqa: F401
from django.http import HttpResponse  # noqa: F401
from rest_framework import viewsets, filters, status  # noqa: F401
from rest_framework.decorators import action  # noqa: F401
from rest_framework.response import Response  # noqa: F401
from authentication.mixins import TenantMixin  # noqa: F401
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


class BonCommandeFournisseurViewSet(TenantMixin, viewsets.ModelViewSet):
    """Bons de commande fournisseur (achats). Distinct du BC CLIENT de ventes.

    - référence numérotée sans trou (préfixe BCF) via references.py ;
    - réceptions partielles : l'action `recevoir` incrémente le stock via
      MouvementStock (ENTREE) pour les quantités reçues uniquement ;
    - les prix d'ACHAT restent internes (jamais sur un document client).
    """
    queryset = BonCommandeFournisseur.objects.select_related(
        'fournisseur', 'created_by',
    ).prefetch_related('lignes__produit').all()
    serializer_class = BonCommandeFournisseurSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference', 'fournisseur__nom', 'note']
    ordering_fields = ['date_creation', 'date_commande', 'statut', 'reference']
    ordering = ['-date_creation']

    def get_permissions(self):
        # QS1 — le PDF (interne) est une LECTURE : il rend exactement les
        # données que `retrieve` expose déjà à tout rôle authentifié. Le
        # laisser en IsResponsableOrAdmin faisait échouer (403) le bouton
        # « PDF (interne) » pour les rôles normaux qui voient pourtant le BCF.
        if self.action in READ_ACTIONS + ['generer_pdf']:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS + [
            'envoyer', 'recevoir', 'annuler',
        ]:
            return [IsResponsableOrAdmin()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        return [IsAdminRole()]

    def perform_create(self, serializer):
        company = self.request.user.company

        def _save(ref):
            return serializer.save(
                reference=ref, company=company,
                created_by=self.request.user,
            )
        create_with_reference(
            BonCommandeFournisseur, 'BCF', company, _save)

    @action(detail=True, methods=['post'], url_path='envoyer')
    def envoyer(self, request, pk=None):
        bc = self.get_object()
        if bc.statut != BonCommandeFournisseur.Statut.BROUILLON:
            return Response(
                {'detail': 'Seul un BCF en brouillon peut être envoyé.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        bc.statut = BonCommandeFournisseur.Statut.ENVOYE
        bc.save(update_fields=['statut'])
        return Response(self.get_serializer(bc).data)

    @action(detail=True, methods=['post'], url_path='annuler')
    def annuler(self, request, pk=None):
        bc = self.get_object()
        if bc.statut == BonCommandeFournisseur.Statut.RECU:
            return Response(
                {'detail': 'Un BCF entièrement reçu ne peut pas être annulé.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        bc.statut = BonCommandeFournisseur.Statut.ANNULE
        bc.save(update_fields=['statut'])
        return Response(self.get_serializer(bc).data)

    @action(detail=True, methods=['post'], url_path='recevoir')
    def recevoir(self, request, pk=None):
        """Réception (totale ou partielle) — incrémente le stock par ENTREE.

        Corps : {"receptions": [{"ligne": <id>, "quantite": <int>}, ...]}.
        Idempotent/sûr : on ne reçoit jamais plus que le reste dû ; le stock
        n'augmente que des quantités effectivement reçues.
        """
        bc = self.get_object()
        if bc.statut in (
            BonCommandeFournisseur.Statut.BROUILLON,
            BonCommandeFournisseur.Statut.ANNULE,
            BonCommandeFournisseur.Statut.RECU,
        ):
            return Response(
                {'detail': (
                    'Seul un BCF envoyé (non encore entièrement reçu) '
                    'peut recevoir des quantités.'
                )},
                status=status.HTTP_400_BAD_REQUEST,
            )

        receptions = request.data.get('receptions') or []
        if not isinstance(receptions, list) or not receptions:
            return Response(
                {'detail': 'Aucune réception fournie.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Index par id de ligne (scopé à ce BC uniquement).
        lignes = {ligne.id: ligne for ligne in bc.lignes.select_related(
            'produit')}
        plan = []
        for rec in receptions:
            try:
                ligne_id = int(rec.get('ligne'))
                qte = int(rec.get('quantite'))
            except (TypeError, ValueError):
                return Response(
                    {'detail': 'Réception invalide.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            ligne = lignes.get(ligne_id)
            if ligne is None:
                return Response(
                    {'detail': f'Ligne {ligne_id} introuvable sur ce BCF.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if qte <= 0:
                continue
            # Plafonnement au reste dû — jamais plus que commandé (idempotence).
            qte = min(qte, ligne.quantite_restante)
            if qte > 0:
                plan.append((ligne, qte))

        if not plan:
            return Response(
                {'detail': 'Rien à recevoir (quantités déjà reçues).'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from django.utils import timezone
        from ..services import record_purchase_price
        today = timezone.now().date()
        with transaction.atomic():
            for ligne, qte in plan:
                # ERR24 — verrou de ligne produit dans la transaction pour que
                # des réceptions concurrentes du même produit ne perdent pas
                # d'incrément (au lieu d'un simple refresh_from_db sans verrou).
                produit = (Produit.objects.select_for_update()
                           .get(pk=ligne.produit_id))
                qte_avant = produit.quantite_stock
                qte_apres = qte_avant + qte
                MouvementStock.objects.create(
                    company=bc.company,
                    produit=produit,
                    type_mouvement=MouvementStock.TypeMouvement.ENTREE,
                    quantite=qte,
                    quantite_avant=qte_avant,
                    quantite_apres=qte_apres,
                    reference=bc.reference,
                    note=f'Réception BCF {bc.reference}',
                    created_by=request.user,
                )
                produit.quantite_stock = qte_apres
                produit.save(update_fields=['quantite_stock'])
                ligne.quantite_recue += qte
                ligne.save(update_fields=['quantite_recue'])
                # N17 — mémorise le prix d'achat (interne) chez ce fournisseur.
                record_purchase_price(
                    company=bc.company, produit=produit,
                    fournisseur=bc.fournisseur,
                    prix_achat=ligne.prix_achat_unitaire, date=today)
            bc.refresh_from_db()
            if bc.est_entierement_recu:
                bc.statut = BonCommandeFournisseur.Statut.RECU
                bc.save(update_fields=['statut'])
        return Response(self.get_serializer(bc).data)

    @action(detail=True, methods=['get'], url_path='pdf')
    def generer_pdf(self, request, pk=None):
        """PDF fournisseur (INTERNE — montre les prix d'achat). Jamais un
        document client."""
        from .utils.pdf_fournisseur import generate_bcf_pdf
        bc = self.get_object()
        pdf_bytes = generate_bcf_pdf(bc)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'inline; filename="{bc.reference}.pdf"')
        return response
