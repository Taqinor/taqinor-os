from rest_framework import serializers
from .models import (
    Produit, Categorie, Fournisseur, MouvementStock, Marque,
    BonCommandeFournisseur, LigneBonCommandeFournisseur,
    EmplacementStock, TransfertStock, PrixFournisseur,
    RetourFournisseur, LigneRetourFournisseur,
    ReceptionFournisseur, LigneReceptionFournisseur,
    FactureFournisseur, LigneFactureFournisseur, PaiementFournisseur,
    InventaireSession, LigneInventaire,
    KitProduit, KitComposant,
    FicheTechnique,
    DocumentConformiteFournisseur, AchatsParametres,
    CategorieFournisseur, ContactFournisseur,
    EcheanceFactureFournisseur, AcompteFournisseur,
    AvoirFournisseur, ImputationAvoirFournisseur,
)


class MarqueSerializer(serializers.ModelSerializer):
    en_usage = serializers.SerializerMethodField()

    class Meta:
        model = Marque
        fields = ['id', 'nom', 'archived', 'en_usage']

    def get_en_usage(self, obj):
        return Produit.objects.filter(company=obj.company, marque=obj.nom).count()


class CategorieSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categorie
        fields = '__all__'


class ContactFournisseurSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactFournisseur
        fields = [
            'id', 'fournisseur', 'nom', 'fonction', 'email', 'telephone',
        ]

    def validate_fournisseur(self, value):
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        if company is not None and value.company_id != company.id:
            raise serializers.ValidationError(
                'Fournisseur hors de votre entreprise.')
        return value


class CategorieFournisseurSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategorieFournisseur
        fields = ['id', 'nom', 'archived']


class FournisseurSerializer(serializers.ModelSerializer):
    # L699 — compteurs LECTURE SEULE : nombre de produits liés et de bons de
    # commande fournisseur associés. Affichés « X produits · Y bons de
    # commande » sur la fiche fournisseur. Annotés en amont quand disponibles
    # (liste), sinon repli sur un count() direct (détail).
    nb_produits = serializers.SerializerMethodField()
    nb_bons_commande = serializers.SerializerMethodField()
    # L698 — message FR explicite quand l'email saisi (création inline incluse)
    # n'est pas un email valide.
    email = serializers.EmailField(
        required=False, allow_null=True, allow_blank=True,
        error_messages={'invalid': 'Adresse email invalide.'})
    # XPUR5 — contacts multiples (lecture) + catégorie affichée + doublon ICE
    # (warning non bloquant, ajouté dynamiquement à la réponse par la vue).
    contacts = ContactFournisseurSerializer(many=True, read_only=True)
    categorie_nom = serializers.CharField(
        source='categorie.nom', read_only=True, default=None)

    class Meta:
        model = Fournisseur
        fields = '__all__'

    def get_nb_produits(self, obj):
        annotated = getattr(obj, 'nb_produits_annot', None)
        if annotated is not None:
            return annotated
        return obj.produits.count()

    def get_nb_bons_commande(self, obj):
        annotated = getattr(obj, 'nb_bons_commande_annot', None)
        if annotated is not None:
            return annotated
        return obj.bons_commande.count()

    def validate_ice(self, value):
        from .services import validate_ice_format
        if value and not validate_ice_format(value):
            raise serializers.ValidationError(
                "Format ICE invalide : l'ICE doit comporter exactement 15 "
                'chiffres.')
        return value


class MouvementStockSerializer(serializers.ModelSerializer):
    produit_nom = serializers.CharField(source='produit.nom', read_only=True)
    created_by_username = serializers.CharField(
        source='created_by.username', read_only=True
    )

    class Meta:
        model = MouvementStock
        fields = '__all__'
        # company is force-assigned in perform_create — never accept it from the body.
        read_only_fields = [
            'quantite_avant', 'quantite_apres', 'created_by', 'date', 'company',
        ]


class ProduitSerializer(serializers.ModelSerializer):
    categorie = CategorieSerializer(read_only=True)
    categorie_id = serializers.PrimaryKeyRelatedField(
        queryset=Categorie.objects.none(),
        source='categorie',
        write_only=True,
        required=False,
        allow_null=True,
    )
    fournisseur = FournisseurSerializer(read_only=True)
    fournisseur_id = serializers.PrimaryKeyRelatedField(
        queryset=Fournisseur.objects.none(),
        source='fournisseur',
        write_only=True,
        required=False,
        allow_null=True,
    )

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get('request')
        if request and hasattr(request.user, 'company_id') and request.user.company_id:
            company = request.user.company
            fields['categorie_id'].queryset = Categorie.objects.filter(company=company)
            fields['fournisseur_id'].queryset = Fournisseur.objects.filter(company=company)
        elif request and request.user.is_superuser:
            fields['categorie_id'].queryset = Categorie.objects.all()
            fields['fournisseur_id'].queryset = Fournisseur.objects.all()
        # Feature D — le prix d'achat (et donc la marge) ne s'expose qu'aux rôles
        # autorisés (Directeur/Admin par défaut ; repli historique pour comptes
        # légacy). Jamais sur un document client. Retiré pour les autres.
        user = getattr(request, 'user', None)
        if user is not None and not getattr(user, 'can_view_buy_prices', True):
            fields.pop('prix_achat', None)
        # FG20 — l'indicateur de MARGE (calculé) est une donnée sensible gardée
        # par ``marge_voir`` (Directeur/Admin par défaut). Sans la permission, le
        # champ est retiré complètement — jamais sur un document client.
        if user is not None and not getattr(user, 'can_view_marge', True):
            fields.pop('marge_pct', None)
        return fields
    # FG20 — marge brute en % ((vente − achat)/vente), arrondie à 1 décimale.
    # None si prix_vente nul/absent ou prix_achat à 0. Donnée sensible : le
    # champ est entièrement retiré pour les rôles sans ``marge_voir``.
    marge_pct = serializers.SerializerMethodField()
    is_low_stock = serializers.SerializerMethodField()
    # L578 — type d'équipement de la catégorie (additif, lecture seule) exposé à
    # plat pour permettre au picker d'équipement de chantier de filtrer un slot
    # (panneaux/onduleur…) par TYPE quel que soit le libellé free-text de la
    # catégorie. Vide (None) quand la catégorie n'est pas typée → comportement
    # historique préservé côté frontend (repli sur la liste BOM complète).
    categorie_type = serializers.CharField(
        source='categorie.type_equipement', read_only=True, allow_null=True)
    categorie_type_display = serializers.SerializerMethodField()
    # N14 — quantité ENGAGÉE par des réservations de chantier (non consommée) et
    # DISPONIBLE = stock total − réservé. Les vues stock + alertes de stock bas
    # tiennent compte de l'engagé-mais-non-consommé.
    quantite_reservee = serializers.SerializerMethodField()
    quantite_disponible = serializers.SerializerMethodField()
    is_low_stock_disponible = serializers.SerializerMethodField()
    nb_mouvements = serializers.SerializerMethodField()
    premiere_date_mouvement = serializers.SerializerMethodField()
    derniere_date_mouvement = serializers.SerializerMethodField()
    # N15 — ventilation du stock par emplacement dans la liste catalogue
    # (lecture seule) pour afficher dépôt/camionnette sans ouvrir le modal
    # Transfert. Map calculée UNE fois par sérialisation (pas de N+1).
    stock_par_emplacement = serializers.SerializerMethodField()

    def validate(self, attrs):
        # Champs personnalisés (T11, L808) : valider/nettoyer le custom_data du
        # produit contre les définitions du module « produit », même chemin que
        # Lead. À la création on valide toujours (champs obligatoires) ; en
        # mise à jour, uniquement si custom_data est fourni.
        is_create = self.instance is None
        if is_create or 'custom_data' in attrs:
            from apps.customfields.serializers import validate_custom_data
            request = self.context.get('request')
            company = getattr(getattr(request, 'user', None), 'company', None)
            if company is not None:
                attrs['custom_data'] = validate_custom_data(
                    'produit', company, attrs.get('custom_data'))
        return attrs

    class Meta:
        model = Produit
        # ERR95 — allowlist EXPLICITE (comme le chemin d'export) plutôt que
        # `__all__` : un nouveau champ sensible ajouté au modèle n'est plus
        # exposé au client par défaut (loi « prix_achat jamais client-facing »).
        # `prix_achat` reste listé mais demeure gardé par permission dans
        # get_fields() (retiré pour les rôles sans can_view_buy_prices). Les
        # champs déclarés (read_only/method) sont ajoutés automatiquement par
        # DRF s'ils figurent dans `fields`.
        fields = [
            # Identité & catalogue
            'id', 'company', 'nom', 'description', 'sku', 'marque',
            # Prix (prix_achat gardé par permission, cf. get_fields)
            'prix_achat', 'prix_vente', 'tva',
            # Stock
            'quantite_stock', 'seuil_alerte', 'is_archived',
            # Relations (lecture imbriquée + écriture par *_id)
            'categorie', 'categorie_id', 'fournisseur', 'fournisseur_id',
            # Garanties
            'garantie', 'garantie_mois', 'garantie_production_mois',
            # Spécifications pompage
            'pompe_cv', 'hmt_m', 'debit_m3j', 'pompe_kw', 'tension_v',
            'courbe_pompe',
            # Dates & data personnalisée
            'date_creation', 'date_mise_a_jour', 'custom_data',
            # FG20 — indicateur de marge (gardé par marge_voir, cf. get_fields)
            'marge_pct',
            # Champs dérivés / calculés (SerializerMethodField, lecture seule)
            'is_low_stock', 'categorie_type', 'categorie_type_display',
            'quantite_reservee', 'quantite_disponible',
            'is_low_stock_disponible', 'nb_mouvements',
            'premiere_date_mouvement', 'derniere_date_mouvement',
            'stock_par_emplacement',
        ]
        # company est posé côté serveur (TenantMixin) — jamais accepté du corps.
        read_only_fields = ['company', 'date_creation', 'date_mise_a_jour']

    def _reserved_map(self):
        """Map {produit_id: quantité réservée} calculée UNE fois par sérialisation
        (évite un N+1 sur la liste produits). Mémoïsée sur l'instance."""
        cache = getattr(self, '_reserved_map_cache', None)
        if cache is not None:
            return cache
        from .services import reserved_quantities
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        cache = reserved_quantities(company) if company is not None else {}
        self._reserved_map_cache = cache
        return cache

    def get_marge_pct(self, obj):
        """Marge brute en % depuis prix_vente/prix_achat (None si indéfinie)."""
        from decimal import Decimal, ROUND_HALF_UP
        vente = obj.prix_vente or Decimal('0')
        achat = obj.prix_achat or Decimal('0')
        if vente <= 0 or achat <= 0:
            return None
        pct = (vente - achat) / vente * Decimal('100')
        return str(pct.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP))

    def get_quantite_reservee(self, obj):
        return self._reserved_map().get(obj.id, 0)

    def get_quantite_disponible(self, obj):
        return obj.quantite_stock - self._reserved_map().get(obj.id, 0)

    def get_categorie_type_display(self, obj):
        # Libellé FR du type d'équipement (None si catégorie non typée).
        cat = obj.categorie
        if cat is None or not cat.type_equipement:
            return None
        return cat.get_type_equipement_display()

    def get_is_low_stock(self, obj):
        # Comportement historique conservé (stock brut vs seuil).
        return obj.seuil_alerte > 0 and obj.quantite_stock <= obj.seuil_alerte

    def get_is_low_stock_disponible(self, obj):
        # N14 — alerte sur le DISPONIBLE (engagé-mais-non-consommé décompté).
        if not obj.seuil_alerte or obj.seuil_alerte <= 0:
            return False
        disponible = obj.quantite_stock - self._reserved_map().get(obj.id, 0)
        return disponible <= obj.seuil_alerte

    def _breakdown_map(self):
        """Map {produit_id: [ventilation par emplacement]} calculée UNE fois
        par sérialisation (évite un N+1 sur la liste produits)."""
        cache = getattr(self, '_breakdown_map_cache', None)
        if cache is not None:
            return cache
        from .services import stock_breakdown_map
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        cache = stock_breakdown_map(company) if company is not None else {}
        self._breakdown_map_cache = cache
        return cache

    def get_stock_par_emplacement(self, obj):
        # Seuls les emplacements détenant du stock sont remontés, pour ne pas
        # alourdir la liste. La camionnette à 0 n'apparaît donc pas.
        rows = self._breakdown_map().get(obj.id, [])
        return [r for r in rows if r['quantite']]

    def get_nb_mouvements(self, obj):
        return getattr(obj, 'nb_mouvements', None)

    def get_premiere_date_mouvement(self, obj):
        val = getattr(obj, 'premiere_date_mouvement', None)
        return val.isoformat() if val else None

    def get_derniere_date_mouvement(self, obj):
        val = getattr(obj, 'derniere_date_mouvement', None)
        return val.isoformat() if val else None


class EmplacementStockSerializer(serializers.ModelSerializer):
    """N15 — emplacement de stock. `company` est posé côté serveur."""

    class Meta:
        model = EmplacementStock
        fields = ['id', 'nom', 'is_principal', 'ordre', 'archived']
        read_only_fields = ['is_principal']


class TransfertStockSerializer(serializers.ModelSerializer):
    produit_nom = serializers.CharField(source='produit.nom', read_only=True)
    source_nom = serializers.CharField(source='source.nom', read_only=True)
    destination_nom = serializers.CharField(
        source='destination.nom', read_only=True)
    created_by_username = serializers.CharField(
        source='created_by.username', read_only=True)

    class Meta:
        model = TransfertStock
        fields = [
            'id', 'produit', 'produit_nom', 'source', 'source_nom',
            'destination', 'destination_nom', 'quantite', 'note',
            'created_by_username', 'date',
        ]
        read_only_fields = ['created_by_username', 'date']


class LigneRetourFournisseurSerializer(serializers.ModelSerializer):
    produit_nom = serializers.CharField(source='produit.nom', read_only=True)
    produit_sku = serializers.CharField(source='produit.sku', read_only=True)

    class Meta:
        model = LigneRetourFournisseur
        fields = ['id', 'produit', 'produit_nom', 'produit_sku', 'quantite',
                  'motif']

    def validate_quantite(self, value):
        if value is None or value <= 0:
            raise serializers.ValidationError('La quantité doit être positive.')
        return value


class RetourFournisseurSerializer(serializers.ModelSerializer):
    lignes = LigneRetourFournisseurSerializer(many=True)
    fournisseur_nom = serializers.CharField(
        source='fournisseur.nom', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    bon_commande_reference = serializers.CharField(
        source='bon_commande.reference', read_only=True)
    created_by_username = serializers.CharField(
        source='created_by.username', read_only=True)

    class Meta:
        model = RetourFournisseur
        fields = [
            'id', 'reference', 'fournisseur', 'fournisseur_nom', 'bon_commande',
            'bon_commande_reference', 'statut', 'statut_display', 'motif',
            'created_by', 'created_by_username', 'date_creation', 'lignes',
        ]
        read_only_fields = [
            'reference', 'statut', 'created_by', 'date_creation',
        ]

    def validate_lignes(self, value):
        if not value:
            raise serializers.ValidationError('Au moins une ligne est requise.')
        return value

    def _validate_company(self, fournisseur, lignes_data):
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        if company is None:
            return
        if fournisseur is not None and fournisseur.company_id != company.id:
            raise serializers.ValidationError(
                {'fournisseur': 'Fournisseur hors de votre entreprise.'})
        for ligne in lignes_data:
            if ligne['produit'].company_id != company.id:
                raise serializers.ValidationError(
                    {'lignes': 'Produit hors de votre entreprise.'})

    def create(self, validated_data):
        lignes_data = validated_data.pop('lignes')
        self._validate_company(validated_data.get('fournisseur'), lignes_data)
        retour = RetourFournisseur.objects.create(**validated_data)
        for ligne in lignes_data:
            LigneRetourFournisseur.objects.create(retour=retour, **ligne)
        return retour


class PrixFournisseurSerializer(serializers.ModelSerializer):
    """N17 — prix d'achat par (produit, fournisseur). INTERNE."""
    fournisseur_nom = serializers.CharField(
        source='fournisseur.nom', read_only=True)
    produit_nom = serializers.CharField(source='produit.nom', read_only=True)

    class Meta:
        model = PrixFournisseur
        fields = [
            'id', 'produit', 'produit_nom', 'fournisseur', 'fournisseur_nom',
            'prix_achat', 'date_dernier_achat', 'delai_livraison_jours',
        ]
        # company posé côté serveur.


class LigneBonCommandeFournisseurSerializer(serializers.ModelSerializer):
    produit_nom = serializers.CharField(source='produit.nom', read_only=True)
    produit_sku = serializers.CharField(source='produit.sku', read_only=True)
    quantite_restante = serializers.IntegerField(read_only=True)
    total_achat = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = LigneBonCommandeFournisseur
        fields = [
            'id', 'produit', 'produit_nom', 'produit_sku', 'quantite',
            'prix_achat_unitaire', 'prix_achat_unitaire_devise',
            'frais_annexes', 'quantite_recue',
            'quantite_restante', 'total_achat',
        ]
        # quantite_recue n'est jamais posée librement : elle évolue uniquement
        # via l'action de réception (perform_create n'accepte que le reste).
        read_only_fields = ['quantite_recue']

    def validate_quantite(self, value):
        if value is None or value <= 0:
            raise serializers.ValidationError('La quantité doit être positive.')
        return value


class BonCommandeFournisseurSerializer(serializers.ModelSerializer):
    lignes = LigneBonCommandeFournisseurSerializer(many=True)
    fournisseur_nom = serializers.CharField(
        source='fournisseur.nom', read_only=True)
    created_by_username = serializers.CharField(
        source='created_by.username', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    total_achat = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)
    est_entierement_recu = serializers.BooleanField(read_only=True)
    # XPUR8 — acomptes versés sur ce BCF (SerializerMethodField : évite une
    # dépendance d'ordre de classe vers AcompteFournisseurSerializer, défini
    # plus bas dans ce module).
    acomptes = serializers.SerializerMethodField()

    class Meta:
        model = BonCommandeFournisseur
        fields = [
            'id', 'reference', 'fournisseur', 'fournisseur_nom', 'statut',
            'statut_display', 'date_commande', 'note', 'devise',
            'taux_change', 'date_livraison_prevue',
            'date_confirmee_fournisseur', 'numero_confirmation_fournisseur',
            'created_by',
            'created_by_username', 'date_creation', 'date_mise_a_jour',
            'lignes', 'total_achat', 'est_entierement_recu', 'acomptes',
        ]
        # company + reference + created_by sont posés côté serveur. La date
        # confirmée/numéro d'accusé n'est modifiable QUE via l'action
        # `confirmer` (XPUR7) — jamais en écriture libre sur le document.
        read_only_fields = [
            'reference', 'created_by', 'date_creation', 'date_mise_a_jour',
            'date_confirmee_fournisseur', 'numero_confirmation_fournisseur',
        ]

    def get_acomptes(self, obj):
        return AcompteFournisseurSerializer(
            obj.acomptes.all(), many=True).data

    def validate_lignes(self, value):
        if not value:
            raise serializers.ValidationError('Au moins une ligne est requise.')
        return value

    def validate_fournisseur(self, value):
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        if company is not None and value.company_id != company.id:
            raise serializers.ValidationError(
                'Fournisseur hors de votre entreprise.')
        return value

    def _validate_company_produits(self, lignes_data):
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        if company is None:
            return
        for ligne in lignes_data:
            produit = ligne['produit']
            if produit.company_id != company.id:
                raise serializers.ValidationError(
                    {'lignes': 'Produit hors de votre entreprise.'})

    def create(self, validated_data):
        from .services import apply_devise_ligne_bcf, compute_date_livraison_prevue
        lignes_data = validated_data.pop('lignes')
        self._validate_company_produits(lignes_data)
        devise = validated_data.get('devise')
        taux = validated_data.get('taux_change')
        # XPUR7 — pré-calcule date_livraison_prevue QUAND elle n'est pas
        # explicitement fournie et qu'un délai est connu (reste modifiable
        # ensuite). No-op sinon (comportement historique).
        if not validated_data.get('date_livraison_prevue'):
            request = self.context.get('request')
            company = getattr(getattr(request, 'user', None), 'company', None)
            derived = compute_date_livraison_prevue(
                company, validated_data.get('fournisseur'),
                validated_data.get('date_commande'), lignes_data)
            if derived:
                validated_data['date_livraison_prevue'] = derived
        bon = BonCommandeFournisseur.objects.create(**validated_data)
        for ligne in lignes_data:
            apply_devise_ligne_bcf(ligne, devise, taux)
            LigneBonCommandeFournisseur.objects.create(
                bon_commande=bon, **ligne)
        return bon

    def update(self, instance, validated_data):
        from .services import apply_devise_ligne_bcf
        # Les écritures sur les lignes ne sont permises qu'en BROUILLON :
        # une fois envoyé/reçu, le contenu commandé est figé.
        lignes_data = validated_data.pop('lignes', None)
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.save()
        if lignes_data is not None:
            if instance.statut != BonCommandeFournisseur.Statut.BROUILLON:
                raise serializers.ValidationError(
                    'Les lignes ne sont modifiables qu\'en brouillon.')
            self._validate_company_produits(lignes_data)
            instance.lignes.all().delete()
            for ligne in lignes_data:
                apply_devise_ligne_bcf(
                    ligne, instance.devise, instance.taux_change)
                LigneBonCommandeFournisseur.objects.create(
                    bon_commande=instance, **ligne)
        return instance


# ── G5 — Réception fournisseur (goods-in) ────────────────────────────────────

class LigneReceptionFournisseurSerializer(serializers.ModelSerializer):
    produit_nom = serializers.CharField(source='produit.nom', read_only=True)
    produit_sku = serializers.CharField(source='produit.sku', read_only=True)

    class Meta:
        model = LigneReceptionFournisseur
        fields = [
            'id', 'ligne_commande', 'produit', 'produit_nom', 'produit_sku',
            'quantite',
            # FG61 — numéros de série à la réception
            'numeros_serie',
            # FG64 — traçabilité lot / péremption
            'numero_lot', 'date_peremption',
        ]
        # produit est dérivé de la ligne de commande côté serveur.
        read_only_fields = ['produit']

    def validate_quantite(self, value):
        if value is None or value <= 0:
            raise serializers.ValidationError('La quantité doit être positive.')
        return value


class ReceptionFournisseurSerializer(serializers.ModelSerializer):
    lignes = LigneReceptionFournisseurSerializer(many=True)
    bon_commande_reference = serializers.CharField(
        source='bon_commande.reference', read_only=True)
    fournisseur_nom = serializers.CharField(
        source='bon_commande.fournisseur.nom', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    recu_par_username = serializers.CharField(
        source='recu_par.username', read_only=True)
    created_by_username = serializers.CharField(
        source='created_by.username', read_only=True)
    total_recu = serializers.IntegerField(read_only=True)

    class Meta:
        model = ReceptionFournisseur
        fields = [
            'id', 'reference', 'bon_commande', 'bon_commande_reference',
            'fournisseur_nom', 'statut', 'statut_display', 'date_reception',
            'note', 'recu_par', 'recu_par_username', 'created_by',
            'created_by_username', 'date_creation', 'lignes', 'total_recu',
        ]
        # company + reference + statut + created_by sont posés côté serveur.
        read_only_fields = [
            'reference', 'statut', 'created_by', 'date_creation',
        ]

    def validate_lignes(self, value):
        if not value:
            raise serializers.ValidationError('Au moins une ligne est requise.')
        return value

    def validate_bon_commande(self, value):
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        if company is not None and value.company_id != company.id:
            raise serializers.ValidationError(
                'Bon de commande hors de votre entreprise.')
        if value.statut == BonCommandeFournisseur.Statut.ANNULE:
            raise serializers.ValidationError(
                'Ce bon de commande est annulé.')
        return value

    def create(self, validated_data):
        lignes_data = validated_data.pop('lignes')
        bon = validated_data['bon_commande']
        # Les lignes de réception se rattachent aux lignes du BCF ; le produit
        # est dérivé de la ligne de commande (jamais du corps de requête).
        bcf_lignes = {ligne.id: ligne for ligne in bon.lignes.all()}
        reception = ReceptionFournisseur.objects.create(**validated_data)
        for ligne in lignes_data:
            ligne_cmd = bcf_lignes.get(ligne['ligne_commande'].id)
            if ligne_cmd is None:
                raise serializers.ValidationError(
                    {'lignes': 'Ligne de commande hors de ce bon de commande.'})
            LigneReceptionFournisseur.objects.create(
                reception=reception, ligne_commande=ligne_cmd,
                produit=ligne_cmd.produit, quantite=ligne['quantite'])
        return reception


# ── G5 — Facture fournisseur / comptes à payer (AP) ──────────────────────────

class LigneFactureFournisseurSerializer(serializers.ModelSerializer):
    produit_nom = serializers.CharField(source='produit.nom', read_only=True)
    total_ht = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = LigneFactureFournisseur
        fields = [
            'id', 'produit', 'produit_nom', 'designation', 'quantite',
            'prix_unitaire_ht', 'total_ht',
        ]


class PaiementFournisseurSerializer(serializers.ModelSerializer):
    mode_display = serializers.CharField(
        source='get_mode_display', read_only=True)
    facture_reference = serializers.CharField(
        source='facture.reference', read_only=True)
    created_by_username = serializers.CharField(
        source='created_by.username', read_only=True)
    # XPUR2 — RAS-TVA : calculée côté serveur (jamais depuis le corps de
    # requête), exposée en lecture pour affichage du net payé.
    montant_net_paye = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = PaiementFournisseur
        fields = [
            'id', 'facture', 'facture_reference', 'montant', 'date_paiement',
            'mode', 'mode_display', 'note', 'created_by', 'created_by_username',
            'date_creation', 'montant_ras_tva', 'taux_ras', 'montant_net_paye',
        ]
        # company + created_by + RAS-TVA posés côté serveur (jamais du corps).
        read_only_fields = [
            'created_by', 'date_creation', 'montant_ras_tva', 'taux_ras',
        ]

    def validate_montant(self, value):
        if value is None or value <= 0:
            raise serializers.ValidationError('Le montant doit être positif.')
        return value

    def validate_facture(self, value):
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        if company is not None and value.company_id != company.id:
            raise serializers.ValidationError(
                'Facture hors de votre entreprise.')
        return value


class EcheanceFactureFournisseurSerializer(serializers.ModelSerializer):
    class Meta:
        model = EcheanceFactureFournisseur
        fields = ['id', 'facture', 'pourcentage', 'montant', 'date_echeance',
                  'date_creation']
        read_only_fields = ['date_creation']


class FactureFournisseurSerializer(serializers.ModelSerializer):
    lignes = LigneFactureFournisseurSerializer(many=True, required=False)
    paiements = PaiementFournisseurSerializer(many=True, read_only=True)
    echeances = EcheanceFactureFournisseurSerializer(many=True, read_only=True)
    fournisseur_nom = serializers.CharField(
        source='fournisseur.nom', read_only=True)
    bon_commande_reference = serializers.CharField(
        source='bon_commande.reference', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    created_by_username = serializers.CharField(
        source='created_by.username', read_only=True)
    total_paye = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)
    solde_du = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)
    # XPUR8 — acomptes fournisseur imputés sur cette facture (0 par défaut).
    total_acomptes_imputes = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)
    # XPUR9 — avoirs fournisseur imputés sur cette facture (0 par défaut).
    total_avoirs_imputes = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = FactureFournisseur
        fields = [
            'id', 'reference', 'fournisseur', 'fournisseur_nom', 'bon_commande',
            'bon_commande_reference', 'ref_fournisseur', 'date_facture',
            'date_echeance', 'montant_ht', 'montant_tva', 'montant_ttc',
            'devise', 'taux_change', 'montant_ttc_devise',
            'type_achat', 'statut', 'statut_display', 'note', 'created_by',
            'created_by_username', 'date_creation', 'date_mise_a_jour',
            'total_acomptes_imputes', 'total_avoirs_imputes',
            'lignes', 'paiements', 'echeances', 'total_paye', 'solde_du',
        ]
        # company + reference + statut + created_by sont posés côté serveur.
        # Le statut découle des paiements (recompute_facture_fournisseur_statut).
        read_only_fields = [
            'reference', 'statut', 'created_by', 'date_creation',
            'date_mise_a_jour',
        ]

    def validate_fournisseur(self, value):
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        if company is not None and value.company_id != company.id:
            raise serializers.ValidationError(
                'Fournisseur hors de votre entreprise.')
        return value

    def validate_bon_commande(self, value):
        if value is None:
            return value
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        if company is not None and value.company_id != company.id:
            raise serializers.ValidationError(
                'Bon de commande hors de votre entreprise.')
        return value

    # DC16 — une facture rattachée à un bon de commande doit être créée via
    # « facturer une réception » (FG56) pour que ses montants soient DÉRIVÉS de
    # la réception (jamais saisis à la main) AVANT le rapprochement 3 voies
    # (FG131) ; on refuse donc la saisie manuelle sur une FF liée à un BCF.
    _MSG_DC16_CREATE = (
        'Une facture rattachée à un bon de commande doit être créée via '
        '« facturer une réception » (receptions-fournisseur/{id}/facturer/) : '
        'ses montants sont dérivés de la réception, jamais saisis à la main.')
    _MSG_DC16_UPDATE = (
        'Les montants d\'une facture liée à un bon de commande sont dérivés de '
        'la réception (FG56) et ne sont pas modifiables à la main.')

    def create(self, validated_data):
        if validated_data.get('bon_commande'):
            raise serializers.ValidationError({'bon_commande': self._MSG_DC16_CREATE})
        from .services import apply_devise_facture
        lignes_data = validated_data.pop('lignes', [])
        # XPUR3 — si un montant TTC en devise est fourni, sa contre-valeur
        # MAD ÉCRASE montant_ttc (comportement historique inchangé quand la
        # facture est en MAD / le champ devise n'est pas renseigné).
        mad = apply_devise_facture(
            validated_data.get('montant_ttc_devise'),
            validated_data.get('devise'), validated_data.get('taux_change'))
        if mad is not None:
            validated_data['montant_ttc'] = mad
        # XPUR6 — auto-dérive date_echeance depuis les conditions de paiement
        # du fournisseur QUAND elle n'est pas explicitement fournie (reste
        # modifiable ensuite). No-op si le fournisseur n'a pas de délai
        # configuré (comportement historique).
        if not validated_data.get('date_echeance'):
            from .services import derive_date_echeance
            fournisseur = validated_data.get('fournisseur')
            date_facture = validated_data.get('date_facture')
            derived = derive_date_echeance(fournisseur, date_facture)
            if derived:
                validated_data['date_echeance'] = derived
        facture = FactureFournisseur.objects.create(**validated_data)
        for ligne in lignes_data:
            LigneFactureFournisseur.objects.create(facture=facture, **ligne)
        return facture

    def update(self, instance, validated_data):
        # DC16 — sur une FF déjà liée à un BCF (typiquement issue de FG56), les
        # montants restent ceux dérivés de la réception : on rejette toute
        # tentative de les écraser à la main.
        if instance.bon_commande_id:
            for champ in ('montant_ht', 'montant_tva', 'montant_ttc'):
                if champ in validated_data and validated_data[champ] != getattr(
                        instance, champ):
                    raise serializers.ValidationError({champ: self._MSG_DC16_UPDATE})
        lignes_data = validated_data.pop('lignes', None)
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.save()
        if lignes_data is not None:
            instance.lignes.all().delete()
            for ligne in lignes_data:
                LigneFactureFournisseur.objects.create(
                    facture=instance, **ligne)
        return instance


# ── FG63 — Session d'inventaire ───────────────────────────────────────────────

class LigneInventaireSerializer(serializers.ModelSerializer):
    produit_nom = serializers.CharField(source='produit.nom', read_only=True)
    ecart = serializers.IntegerField(read_only=True)

    class Meta:
        model = LigneInventaire
        fields = [
            'id', 'produit', 'produit_nom',
            'quantite_theorique', 'quantite_comptee', 'ecart',
        ]


class InventaireSessionSerializer(serializers.ModelSerializer):
    lignes = LigneInventaireSerializer(many=True, required=False)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    created_by_username = serializers.CharField(
        source='created_by.username', read_only=True)

    class Meta:
        model = InventaireSession
        fields = [
            'id', 'reference', 'statut', 'statut_display', 'motif',
            'created_by', 'created_by_username',
            'date_creation', 'date_mise_a_jour', 'lignes',
        ]
        read_only_fields = [
            'reference', 'statut', 'created_by',
            'date_creation', 'date_mise_a_jour',
        ]

    def create(self, validated_data):
        lignes_data = validated_data.pop('lignes', [])
        session = InventaireSession.objects.create(**validated_data)
        for ligne in lignes_data:
            LigneInventaire.objects.create(session=session, **ligne)
        return session

    def update(self, instance, validated_data):
        lignes_data = validated_data.pop('lignes', None)
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.save()
        if lignes_data is not None:
            instance.lignes.all().delete()
            for ligne in lignes_data:
                LigneInventaire.objects.create(session=instance, **ligne)
        return instance


# ── FG66 / DC36 — Kit / nomenclature (BOM) ────────────────────────────────────

class KitComposantSerializer(serializers.ModelSerializer):
    produit_nom = serializers.CharField(source='produit.nom', read_only=True)
    produit_sku = serializers.CharField(source='produit.sku', read_only=True)
    # DC36 — prix de vente catalogue affiché en LECTURE SEULE (jamais stocké sur
    # le kit) ; aucun prix d'achat ici (interne).
    prix_vente = serializers.DecimalField(
        source='produit.prix_vente', max_digits=10, decimal_places=2,
        read_only=True)

    class Meta:
        model = KitComposant
        fields = ['id', 'produit', 'produit_nom', 'produit_sku', 'prix_vente',
                  'quantite']

    def validate_quantite(self, value):
        if value is None or value <= 0:
            raise serializers.ValidationError('La quantité doit être positive.')
        return value


class KitProduitSerializer(serializers.ModelSerializer):
    composants = KitComposantSerializer(many=True)
    nb_composants = serializers.SerializerMethodField()

    class Meta:
        model = KitProduit
        # DC36 — un kit ne porte AUCUN champ prix / marque / TVA : tout vient
        # des composants à l'explosion.
        fields = ['id', 'nom', 'sku', 'description', 'is_archived',
                  'composants', 'nb_composants', 'date_creation',
                  'date_mise_a_jour']
        read_only_fields = ['date_creation', 'date_mise_a_jour']

    def get_nb_composants(self, obj):
        return obj.composants.count()

    def _validate_company(self, composants_data):
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        if company is None:
            return
        for c in composants_data:
            if c['produit'].company_id != company.id:
                raise serializers.ValidationError(
                    {'composants': 'Produit hors de votre entreprise.'})

    def create(self, validated_data):
        composants_data = validated_data.pop('composants', [])
        self._validate_company(composants_data)
        kit = KitProduit.objects.create(**validated_data)
        for c in composants_data:
            KitComposant.objects.create(kit=kit, **c)
        return kit

    def update(self, instance, validated_data):
        composants_data = validated_data.pop('composants', None)
        if composants_data is not None:
            self._validate_company(composants_data)
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.save()
        if composants_data is not None:
            instance.composants.all().delete()
            for c in composants_data:
                KitComposant.objects.create(kit=instance, **c)
        return instance


class FicheTechniqueSerializer(serializers.ModelSerializer):
    """DC35 — datasheet rattachée à un produit. Expose en LECTURE quelques
    champs du produit (marque/garantie/nom) pour éviter au front de re-saisir
    ou re-stocker l'identité : elle vit sur ``Produit`` et n'est jamais copiée
    sur la fiche."""
    produit_nom = serializers.CharField(source='produit.nom', read_only=True)
    produit_marque = serializers.CharField(
        source='produit.marque', read_only=True)
    produit_garantie = serializers.CharField(
        source='produit.garantie', read_only=True)

    class Meta:
        model = FicheTechnique
        fields = [
            'id', 'produit', 'produit_nom', 'produit_marque',
            'produit_garantie', 'pmax_wc', 'voc_v', 'isc_a', 'vmp_v', 'imp_a',
            'rendement_pct', 'pdf', 'date_creation', 'date_mise_a_jour',
        ]
        # company is force-assigned in perform_create — never from the body.
        read_only_fields = ['company', 'date_creation', 'date_mise_a_jour']

    def validate_produit(self, value):
        """Le produit doit appartenir à la société du demandeur (anti
        cross-tenant)."""
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        if company is not None and value.company_id != company.id:
            raise serializers.ValidationError(
                'Produit hors de votre entreprise.')
        return value


# ── XPUR1 — conformité fournisseur & paramètres achats ──────────────────────

class DocumentConformiteFournisseurSerializer(serializers.ModelSerializer):
    type_document_display = serializers.CharField(
        source='get_type_document_display', read_only=True)
    fournisseur_nom = serializers.CharField(
        source='fournisseur.nom', read_only=True)
    est_valide = serializers.SerializerMethodField()

    class Meta:
        model = DocumentConformiteFournisseur
        fields = [
            'id', 'fournisseur', 'fournisseur_nom', 'type_document',
            'type_document_display', 'reference', 'date_emission',
            'date_expiration', 'obligatoire', 'note', 'est_valide',
            'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'created_by', 'date_creation', 'date_modification',
        ]

    def get_est_valide(self, obj):
        return obj.est_valide()

    def validate_fournisseur(self, value):
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        if company is not None and value.company_id != company.id:
            raise serializers.ValidationError(
                'Fournisseur hors de votre entreprise.')
        return value


class AchatsParametresSerializer(serializers.ModelSerializer):
    class Meta:
        model = AchatsParametres
        fields = [
            'id', 'bloquer_paiement_conformite_expiree',
            'date_creation', 'date_modification',
        ]
        read_only_fields = ['date_creation', 'date_modification']


# ── XPUR8 — acomptes fournisseur ─────────────────────────────────────────────

class AcompteFournisseurSerializer(serializers.ModelSerializer):
    mode_display = serializers.CharField(
        source='get_mode_display', read_only=True)
    bon_commande_reference = serializers.CharField(
        source='bon_commande.reference', read_only=True)
    montant_non_consomme = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = AcompteFournisseur
        fields = [
            'id', 'bon_commande', 'bon_commande_reference', 'montant',
            'date_versement', 'mode', 'mode_display', 'montant_consomme',
            'montant_non_consomme', 'facture_imputee', 'note', 'created_by',
            'date_creation',
        ]
        # company + created_by + imputation posés côté serveur.
        read_only_fields = [
            'created_by', 'date_creation', 'montant_consomme',
            'facture_imputee',
        ]

    def validate_montant(self, value):
        if value is None or value <= 0:
            raise serializers.ValidationError('Le montant doit être positif.')
        return value

    def validate_bon_commande(self, value):
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        if company is not None and value.company_id != company.id:
            raise serializers.ValidationError(
                'Bon de commande hors de votre entreprise.')
        return value


# ── XPUR9 — avoir fournisseur (note de crédit AP) ────────────────────────────

class ImputationAvoirFournisseurSerializer(serializers.ModelSerializer):
    facture_reference = serializers.CharField(
        source='facture.reference', read_only=True)

    class Meta:
        model = ImputationAvoirFournisseur
        fields = ['id', 'avoir', 'facture', 'facture_reference', 'montant',
                  'date_creation']
        read_only_fields = ['date_creation']


class AvoirFournisseurSerializer(serializers.ModelSerializer):
    fournisseur_nom = serializers.CharField(
        source='fournisseur.nom', read_only=True)
    retour_reference = serializers.CharField(
        source='retour.reference', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    montant_disponible = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)
    imputations = ImputationAvoirFournisseurSerializer(
        many=True, read_only=True)

    class Meta:
        model = AvoirFournisseur
        fields = [
            'id', 'reference', 'fournisseur', 'fournisseur_nom',
            'facture_origine', 'retour', 'retour_reference', 'montant_ht',
            'montant_tva', 'montant_ttc', 'statut', 'statut_display',
            'montant_impute', 'montant_disponible', 'note', 'created_by',
            'date_creation', 'date_mise_a_jour', 'imputations',
        ]
        # company + reference + montant_impute + statut posés côté serveur
        # (l'imputation avance le statut, jamais une écriture libre).
        read_only_fields = [
            'reference', 'created_by', 'date_creation', 'date_mise_a_jour',
            'montant_impute',
        ]

    def validate_fournisseur(self, value):
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        if company is not None and value.company_id != company.id:
            raise serializers.ValidationError(
                'Fournisseur hors de votre entreprise.')
        return value
