"""Groupe NTWMS — sérialiseurs de la couche entrepôt.

``company`` n'est JAMAIS exposé ni accepté : il est posé côté serveur par
``CompanyScopedModelViewSet`` (règle multi-tenant).
"""
from rest_framework import serializers

from .models_wms import (
    ExpeditionTransporteur, LignePicking, Quai, RendezVousTransporteur,
    UniteLogistique, UniteLogistiqueLigne, VaguePicking,
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

    def get_nb_lignes(self, obj):
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
            'dimensions', 'statut', 'date_scellage', 'scelle_par',
            'est_figee', 'nb_enfants', 'lignes', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'sscc', 'statut', 'date_scellage', 'scelle_par', 'created_at',
            'updated_at',
        ]

    def get_nb_enfants(self, obj):
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

    def get_a_une_etiquette(self, obj):
        # La CLÉ MinIO elle-même n'est jamais exposée (chemin de stockage
        # interne) : le client sait seulement qu'une étiquette existe.
        return bool(obj.etiquette_pdf_key)
