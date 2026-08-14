"""Groupe NTSCM — incidents qualité fournisseur (CRUD) + indicateurs.

Endpoints livrés ici :
  * ``incidents-qualite-fournisseur/`` — CRUD (NTSCM9) ;
  * ``fournisseurs/{id}/otif/`` — OTIF réel (NTSCM8), monté sur le viewset
    fournisseur par mixin ;
  * ``fournisseurs/{id}/delai-mesure/`` — délai réel vs annoncé (NTSCM11) ;
  * ``produits/{id}/comparer-tco/`` — TCO par fournisseur (NTSCM26).

Toutes ces valeurs sont INTERNES (prix d'achat, coûts) : gardées
responsable/admin, jamais dans une sortie client-facing.
"""
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.permissions import (
    IsAdminRole, IsAnyRole, IsResponsableOrAdmin,
)
from core.viewsets import CompanyScopedModelViewSet

from ..models import IncidentQualiteFournisseur

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']


class IncidentQualiteFournisseurSerializer(serializers.ModelSerializer):
    fournisseur_nom = serializers.CharField(
        source='fournisseur.nom', read_only=True, default='')
    est_bloquant = serializers.BooleanField(read_only=True)

    class Meta:
        model = IncidentQualiteFournisseur
        fields = [
            'id', 'fournisseur', 'fournisseur_nom',
            'bon_commande_fournisseur', 'produit', 'retour', 'type_incident',
            'gravite', 'quantite_affectee', 'description', 'date_incident',
            'resolu', 'date_resolution', 'cout_impact_mad', 'declare_par',
            'est_bloquant', 'created_at',
        ]
        # `company` n'est JAMAIS acceptée du corps : le viewset la force.
        read_only_fields = ['declare_par', 'est_bloquant', 'created_at']


class IncidentQualiteFournisseurViewSet(CompanyScopedModelViewSet):
    """NTSCM9 — incidents qualité fournisseur.

    Lecture responsable/admin (le coût d'impact est une donnée INTERNE) ;
    écriture responsable/admin ; suppression admin.
    """
    queryset = IncidentQualiteFournisseur.objects.select_related(
        'fournisseur', 'produit').all()
    serializer_class = IncidentQualiteFournisseurSerializer
    ordering = ['-date_incident', '-id']

    def get_permissions(self):
        if self.action in READ_ACTIONS + WRITE_ACTIONS:
            return [IsResponsableOrAdmin()]
        return [IsAdminRole()]

    def get_queryset(self):
        # Filtrage MANUEL (aucun DjangoFilterBackend branché ici).
        qs = super().get_queryset()
        params = self.request.query_params
        fournisseur = params.get('fournisseur')
        if fournisseur:
            qs = qs.filter(fournisseur_id=fournisseur)
        produit = params.get('produit')
        if produit:
            qs = qs.filter(produit_id=produit)
        gravite = params.get('gravite')
        if gravite:
            qs = qs.filter(gravite=gravite)
        resolu = params.get('resolu')
        if resolu in ('0', 'false', 'False'):
            qs = qs.filter(resolu=False)
        elif resolu in ('1', 'true', 'True'):
            qs = qs.filter(resolu=True)
        return qs

    def perform_create(self, serializer):
        # `company` forcée par TenantMixin ; `declare_par` posé serveur.
        super().perform_create(serializer)
        serializer.instance.declare_par = self.request.user
        serializer.instance.save(update_fields=['declare_par'])


OTIF_SHAPE = {
    'fournisseur_id': serializers.IntegerField(),
    'fenetre_mois': serializers.IntegerField(),
    'debut': serializers.CharField(),
    'total_livraisons': serializers.IntegerField(),
    'nb_otif': serializers.IntegerField(),
    'nb_retard': serializers.IntegerField(),
    'nb_incomplet': serializers.IntegerField(),
    'taux_otif_pct': serializers.CharField(allow_null=True),
}


class ScmFournisseurActionsMixin:
    """NTSCM8 / NTSCM11 — indicateurs montés sur le viewset fournisseur."""

    @extend_schema(responses={
        200: inline_serializer('StockFournisseurOtif', OTIF_SHAPE)})
    @action(detail=True, methods=['get'], url_path='otif',
            permission_classes=[IsAnyRole])
    def otif(self, request, pk=None):
        """NTSCM8 — OTIF réel sur une fenêtre glissante
        (``?fenetre_mois=12``). À l'heure ET complet : une commande complète
        mais livrée en retard n'est PAS OTIF."""
        from ..selectors_fournisseur import otif_fournisseur

        return Response(otif_fournisseur(
            request.user.company, self.get_object(),
            fenetre_mois=request.query_params.get('fenetre_mois')))

    @extend_schema(responses={
        200: inline_serializer('StockFournisseurDelaiMesure', {
            'fournisseur_id': serializers.IntegerField(),
            'produit_id': serializers.IntegerField(allow_null=True),
            'fenetre_mois': serializers.IntegerField(),
            'nb_mesures': serializers.IntegerField(),
            'delai_annonce_jours': serializers.FloatField(allow_null=True),
            'delai_mesure_jours': serializers.FloatField(allow_null=True),
            'ecart_jours': serializers.FloatField(allow_null=True),
            'ecart_type_jours': serializers.FloatField(allow_null=True),
            'ecart_pct': serializers.CharField(allow_null=True),
            'seuil_ecart_pct': serializers.CharField(),
            'utiliser_delai_reel': serializers.BooleanField(),
            'delai_retenu_jours': serializers.FloatField(allow_null=True),
        })})
    @action(detail=True, methods=['get'], url_path='delai-mesure',
            permission_classes=[IsResponsableOrAdmin])
    def delai_mesure(self, request, pk=None):
        """NTSCM11 — délai RÉEL mesuré vs délai ANNONCÉ
        (``?produit=&fenetre_mois=&seuil_ecart_pct=``)."""
        from ..models import Produit
        from ..selectors_fournisseur import delai_mesure_vs_annonce

        company = request.user.company
        produit = None
        produit_id = request.query_params.get('produit')
        if produit_id:
            produit = Produit.objects.filter(
                id=produit_id, company=company).first()
        return Response(delai_mesure_vs_annonce(
            company, self.get_object(), produit,
            fenetre_mois=request.query_params.get('fenetre_mois'),
            seuil_ecart_pct=request.query_params.get('seuil_ecart_pct')))


class ScmProduitTcoMixin:
    """NTSCM26 — colonne TCO du panneau « Comparer fournisseurs » (FG58)."""

    @extend_schema(responses={
        200: inline_serializer('StockProduitComparerTco', {
            'produit': serializers.IntegerField(),
            'cout_rupture_jour': serializers.CharField(),
            'fournisseurs': serializers.ListField(
                child=serializers.DictField()),
        })})
    @action(detail=True, methods=['get'], url_path='comparer-tco',
            permission_classes=[IsResponsableOrAdmin])
    def comparer_tco(self, request, pk=None):
        """TCO par fournisseur : prix NU + coût du retard + coût qualité.

        ``?cout_rupture_jour=`` (défaut 0 : sans coût de rupture paramétré, le
        retard ne pèse rien — jamais un chiffre inventé). Le prix nu reste
        renvoyé à côté du TCO : le TCO le complète, il ne le remplace jamais.
        """
        from ..selectors_fournisseur import comparer_tco_fournisseurs

        cout_jour = request.query_params.get('cout_rupture_jour') or 0
        return Response({
            'produit': self.get_object().id,
            'cout_rupture_jour': str(cout_jour),
            'fournisseurs': comparer_tco_fournisseurs(
                request.user.company, self.get_object(),
                cout_rupture_jour=cout_jour,
                fenetre_mois=request.query_params.get('fenetre_mois')),
        })
