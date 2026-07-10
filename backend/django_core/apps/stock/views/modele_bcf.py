from decimal import Decimal

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from core.viewsets import CompanyScopedModelViewSet
from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from apps.ventes.utils.references import create_with_reference

from ..models import (
    ModeleBonCommandeFournisseur, BonCommandeFournisseur,
    LigneBonCommandeFournisseur, PrixFournisseur,
)
from ..serializers import ModeleBonCommandeFournisseurSerializer

# NOTE: ce module fait partie du découpage de l'ancien views.py monolithe
# (un module par ressource). Comportement et symboles inchangés : le
# package __init__ ré-exporte toutes les vues publiques.

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update', 'destroy']


class ModeleBonCommandeFournisseurViewSet(CompanyScopedModelViewSet):
    """ZPUR3 — Modèles de bon de commande fournisseur réutilisables
    (« Purchase Templates ») : nom + fournisseur optionnel + lignes
    produit/quantité par défaut. L'action `generer` matérialise un BCF
    BROUILLON pré-rempli, éditable avant envoi."""
    queryset = ModeleBonCommandeFournisseur.objects.select_related(
        'fournisseur').prefetch_related('lignes__produit').all()
    serializer_class = ModeleBonCommandeFournisseurSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)

    @action(detail=True, methods=['post'], url_path='generer')
    def generer(self, request, pk=None):
        """ZPUR3 — matérialise un BCF BROUILLON pré-rempli depuis les lignes
        du modèle. Le fournisseur du corps de requête (optionnel) prime sur
        celui du modèle ; l'un des deux doit être renseigné. Prix d'achat
        auto-rempli depuis `PrixFournisseur`/dernier achat, éditable après
        génération."""
        modele = self.get_object()
        company = request.user.company
        fournisseur_id = request.data.get('fournisseur') or modele.fournisseur_id
        if not fournisseur_id:
            return Response(
                {'detail': 'Aucun fournisseur (ni sur le modèle, ni fourni).'},
                status=status.HTTP_400_BAD_REQUEST)
        from ..models import Fournisseur
        fournisseur = Fournisseur.objects.filter(
            id=fournisseur_id, company=company).first()
        if fournisseur is None:
            return Response(
                {'detail': 'Fournisseur introuvable dans cette société.'},
                status=status.HTTP_400_BAD_REQUEST)

        lignes_modele = list(modele.lignes.select_related('produit').all())
        if not lignes_modele:
            return Response(
                {'detail': 'Ce modèle ne contient aucune ligne.'},
                status=status.HTTP_400_BAD_REQUEST)

        created = {}

        def _save(ref):
            bon = BonCommandeFournisseur.objects.create(
                company=company, reference=ref, fournisseur=fournisseur,
                statut=BonCommandeFournisseur.Statut.BROUILLON,
                note=f'Généré depuis le modèle « {modele.nom} »',
                created_by=request.user)
            for ligne in lignes_modele:
                prix_fournisseur = (
                    PrixFournisseur.objects
                    .filter(company=company, produit=ligne.produit,
                            fournisseur=fournisseur)
                    .order_by('-date_dernier_achat')
                    .first())
                prix = (prix_fournisseur.prix_achat if prix_fournisseur
                        else (ligne.produit.prix_achat or Decimal('0')))
                LigneBonCommandeFournisseur.objects.create(
                    bon_commande=bon, produit=ligne.produit,
                    quantite=ligne.quantite, prix_achat_unitaire=prix)
            created['bon'] = bon
            return bon

        create_with_reference(BonCommandeFournisseur, 'BCF', company, _save)
        bon = created['bon']
        from ..serializers import BonCommandeFournisseurSerializer
        return Response(
            BonCommandeFournisseurSerializer(
                bon, context={'request': request}).data,
            status=status.HTTP_201_CREATED)
