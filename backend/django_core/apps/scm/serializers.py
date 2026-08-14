"""Sérialiseurs de planification supply chain (Groupe NTSCM).

``company`` n'est jamais exposée en écriture : posée côté serveur par
``core.viewsets.CompanyScopedModelViewSet``.
"""
from rest_framework import serializers

from .models import ClassificationABC, EvenementDemande, PrevisionDemande


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
