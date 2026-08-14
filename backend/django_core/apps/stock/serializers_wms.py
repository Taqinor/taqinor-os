"""Groupe NTWMS — sérialiseurs de la couche entrepôt.

``company`` n'est JAMAIS exposé ni accepté : il est posé côté serveur par
``CompanyScopedModelViewSet`` (règle multi-tenant).
"""
from rest_framework import serializers

from .models_wms import (
    AlerteRappel, BlocageQualite, DemandeTransfert, ExpeditionTransporteur,
    LignePicking,
    LigneRetourClient, MouvementRebut, PlanChargement, PlanComptageTournant,
    PortailTiersToken, Quai,
    RendezVousTransporteur, RetourClient, UniteLogistique,
    UniteLogistiqueLigne, VaguePicking,
)


class LignePickingSerializer(serializers.ModelSerializer):
    """NTWMS4 — ligne d'une vague de prélèvement (lecture)."""

    produit_nom = serializers.CharField(source='produit.nom', read_only=True)
    produit_sku = serializers.CharField(source='produit.sku', read_only=True)
    bin_code = serializers.CharField(
        source='bin.code', read_only=True, default='')
    numero_lot = serializers.CharField(
        source='lot.numero_lot', read_only=True, default='')
    reste_a_prelever = serializers.IntegerField(read_only=True)

    class Meta:
        model = LignePicking
        fields = [
            'id', 'vague', 'produit', 'produit_nom', 'produit_sku',
            'quantite_demandee', 'quantite_prelevee', 'reste_a_prelever',
            'bin', 'bin_code', 'lot', 'numero_lot', 'installation',
            'bon_commande', 'ordre_parcours',
        ]
        read_only_fields = [
            'vague', 'quantite_prelevee', 'ordre_parcours',
        ]


class VaguePickingSerializer(serializers.ModelSerializer):
    """NTWMS4 — vague de prélèvement multi-source. La référence est posée
    côté serveur (`core.numbering`), jamais acceptée du client."""

    lignes = LignePickingSerializer(many=True, read_only=True)
    cree_par_username = serializers.CharField(
        source='cree_par.username', read_only=True, default='')
    nb_lignes = serializers.SerializerMethodField()

    class Meta:
        model = VaguePicking
        fields = [
            'id', 'reference', 'statut', 'mode_liberation', 'seuil_lignes',
            'note', 'date_lancement', 'date_cloture', 'cree_par',
            'cree_par_username', 'nb_lignes', 'lignes', 'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'reference', 'statut', 'mode_liberation', 'seuil_lignes',
            'date_lancement', 'date_cloture', 'cree_par', 'created_at',
            'updated_at',
        ]

    def get_nb_lignes(self, obj) -> int:
        return obj.lignes.count()


class UniteLogistiqueLigneSerializer(serializers.ModelSerializer):
    """NTWMS6 — contenu d'un colis / d'une palette."""

    produit_nom = serializers.CharField(source='produit.nom', read_only=True)
    numero_lot = serializers.CharField(
        source='lot.numero_lot', read_only=True, default='')

    class Meta:
        model = UniteLogistiqueLigne
        fields = [
            'id', 'unite', 'produit', 'produit_nom', 'quantite', 'lot',
            'numero_lot', 'ligne_picking', 'scanne_le', 'scanne_par',
        ]
        read_only_fields = ['unite', 'scanne_le', 'scanne_par']


class UniteLogistiqueSerializer(serializers.ModelSerializer):
    """NTWMS6 — colis / palette adressable. Le SSCC est GÉNÉRÉ côté serveur
    (norme GS1) : jamais accepté du client."""

    lignes = UniteLogistiqueLigneSerializer(many=True, read_only=True)
    nb_enfants = serializers.SerializerMethodField()
    est_figee = serializers.BooleanField(read_only=True)

    class Meta:
        model = UniteLogistique
        fields = [
            'id', 'type_unite', 'sscc', 'parent', 'vague', 'poids_kg',
            'dimensions', 'statut', 'bin_actuel', 'date_scellage',
            'scelle_par',
            'est_figee', 'nb_enfants', 'lignes', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'sscc', 'statut', 'bin_actuel', 'date_scellage', 'scelle_par',
            'created_at', 'updated_at',
        ]

    def get_nb_enfants(self, obj) -> int:
        return obj.enfants.count()


class QuaiSerializer(serializers.ModelSerializer):
    """NTWMS7 — quai de réception/expédition."""

    emplacement_nom = serializers.CharField(
        source='emplacement.nom', read_only=True, default='')

    class Meta:
        model = Quai
        fields = [
            'id', 'nom', 'type_quai', 'emplacement', 'emplacement_nom',
            'actif',
        ]

    def validate_emplacement(self, value):
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        if company is not None and value.company_id != company.id:
            raise serializers.ValidationError(
                'Emplacement introuvable dans cette société.')
        return value


class RendezVousTransporteurSerializer(serializers.ModelSerializer):
    """NTWMS7 — créneau transporteur sur un quai.

    Le chevauchement est refusé PAR LE SERVEUR (garde dans
    ``RendezVousTransporteur.save()``) : ce sérialiseur ne fait que traduire
    le refus en 400 lisible."""

    quai_nom = serializers.CharField(
        source='quai.nom', read_only=True, default='')
    transporteur_nom = serializers.CharField(
        source='transporteur.nom', read_only=True, default='')

    class Meta:
        model = RendezVousTransporteur
        fields = [
            'id', 'quai', 'quai_nom', 'transporteur', 'transporteur_nom',
            'reference_livraison', 'date_heure_debut', 'date_heure_fin',
            'statut', 'chauffeur_nom', 'immatriculation', 'note',
            'date_arrivee',
        ]
        read_only_fields = ['date_arrivee']

    def validate_quai(self, value):
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        if company is not None and value.company_id != company.id:
            raise serializers.ValidationError(
                'Quai introuvable dans cette société.')
        return value

    def validate(self, attrs):
        debut = attrs.get(
            'date_heure_debut', getattr(self.instance, 'date_heure_debut', None))
        fin = attrs.get(
            'date_heure_fin', getattr(self.instance, 'date_heure_fin', None))
        if debut and fin and fin <= debut:
            raise serializers.ValidationError(
                {'date_heure_fin': 'La fin doit être postérieure au début.'})
        return attrs


class ExpeditionTransporteurSerializer(serializers.ModelSerializer):
    """NTWMS9 — expédition d'une unité logistique par un transporteur.

    Le numéro de suivi et la clé d'étiquette sont POSÉS PAR LE SERVEUR (via le
    connecteur) : jamais acceptés du client."""

    sscc = serializers.CharField(
        source='unite_logistique.sscc', read_only=True, default='')
    transporteur_nom = serializers.CharField(
        source='transporteur.nom', read_only=True, default='')
    a_une_etiquette = serializers.SerializerMethodField()

    class Meta:
        model = ExpeditionTransporteur
        fields = [
            'id', 'unite_logistique', 'sscc', 'transporteur_provider',
            'transporteur', 'transporteur_nom', 'numero_suivi', 'cout_reel',
            'statut', 'destination', 'date_expedition', 'a_une_etiquette',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'numero_suivi', 'statut', 'date_expedition', 'created_at',
            'updated_at',
        ]

    def get_a_une_etiquette(self, obj) -> bool:
        # La CLÉ MinIO elle-même n'est jamais exposée (chemin de stockage
        # interne) : le client sait seulement qu'une étiquette existe.
        return bool(obj.etiquette_pdf_key)


class PlanComptageTournantSerializer(serializers.ModelSerializer):
    """NTWMS13 — fréquence de recomptage d'une classe ABC."""

    class Meta:
        model = PlanComptageTournant
        fields = [
            'id', 'classe_abc', 'frequence_jours', 'actif',
            'date_dernier_comptage',
        ]
        read_only_fields = ['date_dernier_comptage']

    def validate_frequence_jours(self, value):
        if value is None or int(value) <= 0:
            raise serializers.ValidationError(
                'La fréquence doit être un nombre de jours positif.')
        return value


class AlerteRappelSerializer(serializers.ModelSerializer):
    """NTWMS17 — rappel produit/lot. Le statut et l'auteur sont posés côté
    serveur (jamais acceptés du corps de requête)."""

    produit_nom = serializers.CharField(source='produit.nom', read_only=True)
    numero_lot = serializers.CharField(
        source='lot.numero_lot', read_only=True, default='')

    class Meta:
        model = AlerteRappel
        fields = [
            'id', 'produit', 'produit_nom', 'lot', 'numero_lot', 'motif',
            'date_declenchement', 'statut', 'declenchee_par', 'date_cloture',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'statut', 'declenchee_par', 'date_cloture', 'date_declenchement',
            'created_at', 'updated_at',
        ]

    def validate_motif(self, value):
        if not (value or '').strip():
            raise serializers.ValidationError(
                'Le motif du rappel est obligatoire.')
        return value


class PortailTiersTokenSerializer(serializers.ModelSerializer):
    """NTWMS20 — jeton du portail 3PL. Le jeton lui-même est GÉNÉRÉ côté
    serveur et n'est jamais accepté du client ; il n'est lisible que par les
    utilisateurs ERP autorisés qui envoient le lien au dépositaire."""

    lien_public = serializers.SerializerMethodField()
    est_valide = serializers.BooleanField(read_only=True)

    class Meta:
        model = PortailTiersToken
        fields = [
            'id', 'tiers_nom', 'token', 'lien_public', 'expires_at',
            'revoked', 'est_valide', 'last_used_at', 'created_at',
        ]
        read_only_fields = ['token', 'last_used_at', 'created_at']

    def get_lien_public(self, obj) -> str:
        return f'/api/django/stock/public/tiers/{obj.token}/solde/'

    def validate_tiers_nom(self, value):
        if not (value or '').strip():
            raise serializers.ValidationError(
                'Nommez le dépositaire concerné par ce jeton.')
        return value


class BlocageQualiteSerializer(serializers.ModelSerializer):
    """NTWMS31 — blocage qualité (quarantaine). Le statut et l'auteur sont
    posés côté serveur ; la levée passe par l'action dédiée."""

    produit_nom = serializers.CharField(source='produit.nom', read_only=True)
    bin_code = serializers.CharField(
        source='bin.code', read_only=True, default='')

    class Meta:
        model = BlocageQualite
        fields = [
            'id', 'produit', 'produit_nom', 'quantite', 'bin', 'bin_code',
            'lot', 'reception', 'non_conformite', 'statut', 'motif',
            'bloque_par', 'leve_par', 'date_levee', 'created_at',
        ]
        read_only_fields = [
            'statut', 'bloque_par', 'leve_par', 'date_levee', 'created_at',
        ]


class PlanChargementSerializer(serializers.ModelSerializer):
    """NTWMS26 — plan de chargement camion. La référence est posée côté
    serveur ; les unités s'ajoutent par l'action dédiée (qui renvoie
    l'avertissement de capacité)."""

    nb_unites = serializers.SerializerMethodField()

    class Meta:
        model = PlanChargement
        fields = [
            'id', 'reference', 'livraison', 'expedition', 'vehicule',
            'unites_logistiques', 'nb_unites', 'capacite_kg', 'capacite_m3',
            'statut', 'note', 'cree_par', 'created_at',
        ]
        read_only_fields = [
            'reference', 'unites_logistiques', 'cree_par', 'created_at',
        ]

    def get_nb_unites(self, obj) -> int:
        return obj.unites_logistiques.count()


class MouvementRebutSerializer(serializers.ModelSerializer):
    """NTWMS24 — déclaration de perte motivée. La valeur de perte et le
    mouvement de stock sont posés côté serveur (jamais acceptés du client) ;
    la valeur reste INTERNE."""

    produit_nom = serializers.CharField(source='produit.nom', read_only=True)
    bin_code = serializers.CharField(
        source='bin.code', read_only=True, default='')
    motif_libelle = serializers.CharField(
        source='get_motif_display', read_only=True)

    class Meta:
        model = MouvementRebut
        fields = [
            'id', 'produit', 'produit_nom', 'quantite', 'motif',
            'motif_libelle', 'bin', 'bin_code', 'valeur_perte', 'mouvement',
            'note', 'declare_par', 'created_at',
        ]
        read_only_fields = [
            'valeur_perte', 'mouvement', 'declare_par', 'created_at',
        ]


class LigneRetourClientSerializer(serializers.ModelSerializer):
    """NTWMS23 — ligne d'un retour client (lecture)."""

    produit_nom = serializers.CharField(source='produit.nom', read_only=True)
    bin_code = serializers.CharField(
        source='bin.code', read_only=True, default='')

    class Meta:
        model = LigneRetourClient
        fields = [
            'id', 'retour', 'produit', 'produit_nom', 'quantite',
            'etat_constate', 'bin', 'bin_code', 'stock_mouvemente', 'note',
        ]
        read_only_fields = ['retour', 'stock_mouvemente']


class RetourClientSerializer(serializers.ModelSerializer):
    """NTWMS23 — retour client (RMA). Référence et statut posés côté
    serveur ; les lignes sont fournies à la création."""

    lignes = LigneRetourClientSerializer(many=True, read_only=True)
    client_nom = serializers.CharField(source='client.nom', read_only=True)

    class Meta:
        model = RetourClient
        fields = [
            'id', 'reference', 'client', 'client_nom', 'chantier', 'ticket',
            'statut', 'motif', 'date_reception', 'date_inspection',
            'cree_par', 'lignes', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'reference', 'statut', 'date_reception', 'date_inspection',
            'cree_par', 'created_at', 'updated_at',
        ]


class DemandeTransfertSerializer(serializers.ModelSerializer):
    """NTWMS21 — demande d'approbation d'un transfert de valeur. Statut,
    valeur et décideur sont posés côté serveur."""

    produit_nom = serializers.CharField(source='produit.nom', read_only=True)
    source_nom = serializers.CharField(
        source='emplacement_source.nom', read_only=True, default='')
    destination_nom = serializers.CharField(
        source='emplacement_destination.nom', read_only=True, default='')

    class Meta:
        model = DemandeTransfert
        fields = [
            'id', 'produit', 'produit_nom', 'quantite', 'emplacement_source',
            'source_nom', 'emplacement_destination', 'destination_nom',
            'statut', 'motif', 'valeur_estimee', 'demande_par',
            'approuve_par', 'date_decision', 'transfert', 'created_at',
        ]
        read_only_fields = [
            'statut', 'valeur_estimee', 'demande_par', 'approuve_par',
            'date_decision', 'transfert', 'created_at',
        ]
