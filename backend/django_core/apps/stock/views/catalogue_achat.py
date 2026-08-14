"""NTP2P3 — Catalogue interne d'achat pour les DEMANDEURS.

Vue LECTURE SEULE du catalogue produit destinée à peupler l'écran de demande
d'achat (``installations.DemandeAchat``, FG310) : un demandeur non-admin doit
pouvoir choisir un article sans jamais voir la MARGE.

Champs exposés — et RIEN d'autre :
    ``id``, ``nom``, ``sku``, ``categorie`` (+ libellé), ``fournisseur_prefere``
    (+ nom) et ``prix_achat_dernier``.

``prix_vente`` n'est JAMAIS sérialisé ici : sans prix de vente, aucune marge
n'est calculable côté client, ce qui EST le critère d'acceptation NTP2P3. Le
prix d'achat, lui, est la donnée utile au demandeur pour estimer sa réquisition
— il reste une donnée INTERNE (jamais un document client, cf. règle
``prix_achat``).

``prix_achat_dernier`` = le tarif ``PrixFournisseur`` le plus récemment acheté
(``date_dernier_achat``), avec repli sur ``Produit.prix_achat``.
"""
from django.db.models import Q
from rest_framework import serializers, viewsets

from authentication.permissions import IsAnyRole
from core.mixins import TenantMixin

from ..models import Produit


class CatalogueAchatSerializer(serializers.ModelSerializer):
    """NTP2P3 — projection MINIMALE du produit pour un demandeur.

    Liste de champs volontairement FERMÉE (jamais ``prix_vente``, jamais
    ``tva``, jamais de champ dérivable en marge)."""
    categorie_nom = serializers.CharField(
        source='categorie.nom', read_only=True, default=None)
    fournisseur_prefere = serializers.IntegerField(
        source='fournisseur_id', read_only=True, default=None)
    fournisseur_prefere_nom = serializers.CharField(
        source='fournisseur.nom', read_only=True, default=None)
    prix_achat_dernier = serializers.SerializerMethodField()

    class Meta:
        model = Produit
        fields = [
            'id', 'nom', 'sku', 'categorie', 'categorie_nom',
            'fournisseur_prefere', 'fournisseur_prefere_nom',
            'prix_achat_dernier',
        ]
        read_only_fields = fields

    def get_prix_achat_dernier(self, obj):
        """Dernier prix d'achat connu : tarif fournisseur le plus récent,
        sinon le prix d'achat catalogue du produit."""
        tarifs = getattr(obj, '_tarifs_recents', None)
        if tarifs is None:
            tarifs = list(
                obj.prix_fournisseurs.order_by(
                    '-date_dernier_achat', '-id')[:1])
        if tarifs and tarifs[0].prix_achat:
            return tarifs[0].prix_achat
        return obj.prix_achat


class CatalogueAchatViewSet(TenantMixin, viewsets.ReadOnlyModelViewSet):
    """NTP2P3 — catalogue d'achat en LECTURE SEULE, scopé société.

    Ouvert à TOUS les rôles (``IsAnyRole``) : un demandeur terrain doit pouvoir
    composer sa réquisition. Aucune écriture n'est exposée (ReadOnly).

    Filtres : ``?q=`` (nom / SKU / catégorie), ``?categorie=<id>``,
    ``?fournisseur=<id>``.
    """
    serializer_class = CatalogueAchatSerializer
    permission_classes = [IsAnyRole]
    queryset = Produit.objects.select_related(
        'categorie', 'fournisseur').filter(is_archived=False)

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        recherche = (params.get('q') or '').strip()
        if recherche:
            qs = qs.filter(
                Q(nom__icontains=recherche)
                | Q(sku__icontains=recherche)
                | Q(categorie__nom__icontains=recherche))
        categorie = params.get('categorie')
        if categorie:
            qs = qs.filter(categorie_id=categorie)
        fournisseur = params.get('fournisseur')
        if fournisseur:
            qs = qs.filter(fournisseur_id=fournisseur)
        return qs.order_by('nom', 'id')
