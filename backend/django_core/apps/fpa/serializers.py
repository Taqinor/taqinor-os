from rest_framework import serializers

from .models import (
    CycleBudgetaire, Departement, LigneBudgetDepartement,
    SoumissionBudgetDepartement,
)


class DepartementSerializer(serializers.ModelSerializer):
    responsable_nom = serializers.SerializerMethodField()

    class Meta:
        model = Departement
        fields = [
            'id', 'company', 'code', 'nom', 'responsable', 'responsable_nom',
            'parent', 'actif', 'date_creation',
        ]
        read_only_fields = ['id', 'company', 'date_creation']

    def get_responsable_nom(self, obj):
        if obj.responsable_id:
            return (getattr(obj.responsable, 'get_full_name', lambda: '')()
                    or obj.responsable.username)
        return ''


class CycleBudgetaireSerializer(serializers.ModelSerializer):
    exercice_label = serializers.SerializerMethodField()

    class Meta:
        model = CycleBudgetaire
        fields = [
            'id', 'company', 'nom', 'exercice_comptable_id', 'exercice_label',
            'date_debut', 'date_fin', 'statut', 'type_cycle', 'date_creation',
        ]
        read_only_fields = ['id', 'company', 'statut', 'date_creation']

    def get_exercice_label(self, obj):
        from apps.compta.selectors import get_exercice_label

        return get_exercice_label(obj.company, obj.exercice_comptable_id)


class LigneBudgetDepartementSerializer(serializers.ModelSerializer):
    class Meta:
        model = LigneBudgetDepartement
        fields = [
            'id', 'company', 'cycle', 'departement', 'categorie', 'mois',
            'montant_prevu', 'commentaire', 'date_modification',
        ]
        read_only_fields = ['id', 'company', 'date_modification']


class SoumissionBudgetDepartementSerializer(serializers.ModelSerializer):
    class Meta:
        model = SoumissionBudgetDepartement
        fields = [
            'id', 'company', 'cycle', 'departement', 'statut', 'motif_rejet',
            'soumis_par', 'soumis_le', 'valide_par', 'valide_le',
        ]
        read_only_fields = fields
