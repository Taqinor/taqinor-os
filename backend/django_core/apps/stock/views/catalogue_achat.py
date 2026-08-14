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
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.permissions import IsAnyRole
from core.mixins import TenantMixin

from ..models import FavorisCatalogueAchat, Produit


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

    @extend_schema_field(serializers.DecimalField(max_digits=12, decimal_places=2))
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
    ``?fournisseur=<id>``, ``?recent=1`` (NTP2P22 — « déjà commandé
    récemment » : restreint aux articles que CET employé a déjà demandés).
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
        if params.get('recent') in ('1', 'true', 'True'):
            qs = qs.filter(id__in=self._produits_recents(limite=50))
        return qs.order_by('nom', 'id')

    def _produits_recents(self, *, limite=5):
        """Derniers produits demandés par l'appelant.

        Lecture cross-app par ``installations.selectors`` UNIQUEMENT (jamais
        un import de ``installations.models``)."""
        from apps.installations.selectors import produits_recemment_demandes
        return produits_recemment_demandes(
            self.request.user.company, self.request.user.pk, limite=limite)

    # Garde EXPLICITE sur l'action (ratchet `test_action_permissions`) :
    # même palier que le viewset, mais déclaré ici pour qu'une action ne
    # puisse jamais hériter d'un palier par accident.
    @action(detail=False, methods=['get', 'put'],
            permission_classes=[IsAnyRole])
    def favoris(self, request):
        """NTP2P22 — favoris du demandeur pour l'écran de demande d'achat.

        ``GET`` renvoie ``{'epingles', 'recents', 'produit_ids'}`` où
        ``produit_ids`` est l'ordre d'affichage effectif : les articles
        ÉPINGLÉS d'abord, puis les 5 derniers demandés (dédoublonnés) — c'est
        ce qui met « les 5 derniers produits demandés en tête de liste ».

        ``PUT`` remplace la liste épinglée (``{"produit_ids": [1, 2]}``). Les
        ids sont validés contre le catalogue de la SOCIÉTÉ : un id étranger
        est silencieusement écarté, jamais stocké."""
        company = request.user.company
        if request.method == 'PUT':
            demandes = request.data.get('produit_ids') or []
            if not isinstance(demandes, list):
                demandes = []
            valides = list(Produit.objects.filter(
                company=company, id__in=[
                    i for i in demandes if isinstance(i, int)]
            ).values_list('id', flat=True))
            # Conserve l'ordre demandé par l'utilisateur.
            ordonnes = [i for i in demandes if i in set(valides)]
            favoris, _ = FavorisCatalogueAchat.objects.get_or_create(
                company=company, utilisateur=request.user,
                defaults={'produit_ids': ordonnes})
            if favoris.produit_ids != ordonnes:
                favoris.produit_ids = ordonnes
                favoris.save(update_fields=['produit_ids', 'updated_at'])
        else:
            favoris = FavorisCatalogueAchat.objects.filter(
                company=company, utilisateur=request.user).first()

        epingles = list(getattr(favoris, 'produit_ids', None) or [])
        recents = self._produits_recents(limite=5)
        vus, ordre = set(), []
        for produit_id in list(epingles) + list(recents):
            if produit_id in vus:
                continue
            vus.add(produit_id)
            ordre.append(produit_id)
        return Response({
            'epingles': epingles,
            'recents': recents,
            'produit_ids': ordre,
        })
