"""Sérialiseurs de planification supply chain (Groupe NTSCM).

``company`` n'est jamais exposée en écriture : posée côté serveur par
``core.viewsets.CompanyScopedModelViewSet``.
"""
from rest_framework import serializers

from .models import (
    ClassificationABC, CyclePlanificationSOP, EvenementDemande, LigneDemandeSOP,
    LigneOffreSOP, PolitiqueStock, PrevisionDemande,
)


class PrevisionDemandeSerializer(serializers.ModelSerializer):
    methode_display = serializers.CharField(
        source='get_methode_display', read_only=True)
    produit_nom = serializers.CharField(
        source='produit.nom', read_only=True)
    genere_par_nom = serializers.CharField(
        source='genere_par.username', read_only=True, default=None)

    class Meta:
        model = PrevisionDemande
        fields = [
            'id', 'produit', 'produit_nom', 'segment', 'periode',
            'quantite_prevue', 'methode', 'methode_display',
            'genere_le', 'genere_par', 'genere_par_nom',
        ]
        read_only_fields = ['id', 'genere_le', 'genere_par']


class EvenementDemandeSerializer(serializers.ModelSerializer):
    type_evenement_display = serializers.CharField(
        source='get_type_evenement_display', read_only=True)
    produit_nom = serializers.CharField(
        source='produit.nom', read_only=True, default=None)
    categorie_nom = serializers.CharField(
        source='categorie.nom', read_only=True, default=None)

    class Meta:
        model = EvenementDemande
        fields = [
            'id', 'produit', 'produit_nom', 'categorie', 'categorie_nom',
            'date_debut', 'date_fin', 'impact_pct', 'libelle',
            'type_evenement', 'type_evenement_display', 'date_creation',
        ]
        read_only_fields = ['id', 'date_creation']

    def validate(self, attrs):
        debut = attrs.get('date_debut', getattr(self.instance, 'date_debut', None))
        fin = attrs.get('date_fin', getattr(self.instance, 'date_fin', None))
        if debut and fin and fin < debut:
            raise serializers.ValidationError(
                {'date_fin': 'Doit être postérieure ou égale à date_debut.'})
        return attrs


class ClassificationABCSerializer(serializers.ModelSerializer):
    produit_nom = serializers.CharField(source='produit.nom', read_only=True)
    produit_sku = serializers.CharField(
        source='produit.sku', read_only=True, default=None)

    class Meta:
        model = ClassificationABC
        fields = [
            'id', 'produit', 'produit_nom', 'produit_sku', 'classe',
            'valeur_cumulee_ht', 'part_valeur_pct', 'rang', 'fenetre_mois',
            'calcule_le',
        ]
        read_only_fields = fields


class PolitiqueStockSerializer(serializers.ModelSerializer):
    produit_nom = serializers.CharField(source='produit.nom', read_only=True)

    class Meta:
        model = PolitiqueStock
        fields = [
            'id', 'produit', 'produit_nom', 'classe_abc', 'service_level_pct',
            'stock_min', 'stock_max', 'point_commande',
            'stock_securite_calcule', 'stock_securite_manuel', 'revise_le',
        ]
        # Champs dérivés en LECTURE SEULE — écrits uniquement par
        # ``services.recalculer_politiques_stock``. ``service_level_pct``,
        # ``stock_min``/``stock_max``/``stock_securite_manuel`` restent
        # éditables (overrides acheteur).
        read_only_fields = [
            'id', 'classe_abc', 'point_commande', 'stock_securite_calcule',
            'revise_le',
        ]


class CyclePlanificationSOPSerializer(serializers.ModelSerializer):
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    anime_par_nom = serializers.CharField(
        source='anime_par.username', read_only=True, default=None)

    class Meta:
        model = CyclePlanificationSOP
        fields = [
            'id', 'periode', 'statut', 'statut_display', 'date_reunion',
            'anime_par', 'anime_par_nom', 'notes_reunion', 'date_creation',
        ]
        # ``statut`` ne se modifie JAMAIS par PATCH direct : le cycle de vie
        # passe exclusivement par l'action ``avancer-statut``
        # (``services.avancer_statut_cycle``), qui applique la machine à
        # états et journalise la transition (même patron que
        # ``ReclamationSerializer``/``apps.litiges``).
        read_only_fields = ['id', 'statut', 'date_creation']

    def validate_periode(self, value):
        # ``company`` n'est pas dans ``fields`` (posée côté serveur) : le
        # validateur ``UniqueConstraint`` auto-généré par DRF ne peut donc pas
        # couvrir (company, periode) — validation manuelle explicite pour
        # renvoyer un 400 propre plutôt qu'un ``IntegrityError`` non attrapé.
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        if company is not None:
            qs = CyclePlanificationSOP.objects.filter(company=company, periode=value)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    f'Un cycle S&OP existe déjà pour la période {value}.')
        return value


class LigneDemandeSOPSerializer(serializers.ModelSerializer):
    produit_nom = serializers.CharField(source='produit.nom', read_only=True)

    class Meta:
        model = LigneDemandeSOP
        fields = [
            'id', 'cycle', 'produit', 'produit_nom',
            'quantite_prevision_systeme', 'quantite_ajustee_commercial',
            'motif_ajustement', 'quantite_finale',
        ]
        # Snapshot gelé (NTSCM13) : seul l'ajustement commercial est
        # modifiable, et UNIQUEMENT via l'action dédiée
        # ``CyclePlanificationSOPViewSet.ajuster_demande`` (jamais un PATCH
        # générique sur cette ressource — le motif doit toujours accompagner
        # l'ajustement, une contrainte qu'un PATCH partiel ne peut pas garantir).
        read_only_fields = [
            'id', 'cycle', 'produit', 'produit_nom',
            'quantite_prevision_systeme', 'quantite_ajustee_commercial',
            'motif_ajustement', 'quantite_finale',
        ]


class LigneOffreSOPSerializer(serializers.ModelSerializer):
    produit_nom = serializers.CharField(source='produit.nom', read_only=True)
    quantite_finale_demande = serializers.SerializerMethodField()

    class Meta:
        model = LigneOffreSOP
        fields = [
            'id', 'cycle', 'produit', 'produit_nom',
            'stock_disponible_snapshot', 'capacite_appro_fournisseur_estimee',
            'ecart_offre_demande', 'quantite_finale_demande',
        ]
        read_only_fields = fields

    def get_quantite_finale_demande(self, obj):
        # Snapshot demande (NTSCM13) du même produit sur ce cycle — pratique
        # à l'écran sans un second appel réseau. None si pas encore gelée.
        ligne_demande = LigneDemandeSOP.objects.filter(
            cycle_id=obj.cycle_id, produit_id=obj.produit_id).first()
        return ligne_demande.quantite_finale if ligne_demande else None
