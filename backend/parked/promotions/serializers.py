from rest_framework import serializers

from .models import ReglexPromotion


class ReglexPromotionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReglexPromotion
        fields = [
            'id', 'nom', 'type_regle', 'actif', 'priorite', 'cumulable',
            'categorie', 'produit', 'montant_min_panier',
            'remise_pct', 'remise_montant', 'n_achete', 'm_paye',
            'heure_debut', 'heure_fin', 'jours_semaine',
            'date_debut', 'date_fin',
        ]

    def validate(self, attrs):
        type_regle = attrs.get(
            'type_regle', getattr(self.instance, 'type_regle', None))
        n_achete = attrs.get('n_achete', getattr(self.instance, 'n_achete', None))
        m_paye = attrs.get('m_paye', getattr(self.instance, 'm_paye', None))
        if type_regle == ReglexPromotion.TypeRegle.N_POUR_M:
            if not n_achete or not m_paye:
                raise serializers.ValidationError(
                    'n_achete et m_paye sont requis pour une règle N pour M.')
            if n_achete <= m_paye:
                raise serializers.ValidationError(
                    'n_achete doit être strictement supérieur à m_paye.')
        return attrs
