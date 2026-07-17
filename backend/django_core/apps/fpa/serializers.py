from rest_framework import serializers

from .models import (
    CommentaireVariance, CycleBudgetaire, Departement, HypotheseRecrutement,
    LigneBudgetDepartement, LignePrevisionGlissante, LigneScenario,
    MappingCategorieCompte, PrevisionGlissante, ScenarioBudgetaire,
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


class LignePrevisionGlissanteSerializer(serializers.ModelSerializer):
    class Meta:
        model = LignePrevisionGlissante
        fields = [
            'id', 'company', 'prevision', 'mois_relatif', 'categorie',
            'montant_prevu', 'source',
        ]
        read_only_fields = ['id', 'company']


class PrevisionGlissanteSerializer(serializers.ModelSerializer):
    lignes = LignePrevisionGlissanteSerializer(many=True, read_only=True)

    class Meta:
        model = PrevisionGlissante
        fields = [
            'id', 'company', 'date_reference', 'horizon_mois', 'departement',
            'date_creation', 'date_modification', 'lignes',
        ]
        read_only_fields = ['id', 'company', 'date_creation', 'date_modification']


class HypotheseRecrutementSerializer(serializers.ModelSerializer):
    est_engage = serializers.BooleanField(read_only=True)

    class Meta:
        model = HypotheseRecrutement
        fields = [
            'id', 'company', 'prevision_glissante', 'poste', 'departement',
            'date_effet', 'salaire_brut_estime', 'type_mouvement', 'statut',
            'est_engage', 'date_creation',
        ]
        read_only_fields = ['id', 'company', 'date_creation']


class LigneScenarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = LigneScenario
        fields = [
            'id', 'company', 'scenario', 'ligne_budget', 'categorie',
            'delta_pct', 'delta_montant', 'raison',
        ]
        read_only_fields = ['id', 'company']


class ScenarioBudgetaireSerializer(serializers.ModelSerializer):
    lignes = LigneScenarioSerializer(many=True, read_only=True)

    class Meta:
        model = ScenarioBudgetaire
        fields = [
            'id', 'company', 'cycle', 'nom', 'description', 'statut',
            'est_scenario_base', 'date_creation', 'lignes',
        ]
        read_only_fields = ['id', 'company', 'date_creation']


class CommentaireVarianceSerializer(serializers.ModelSerializer):
    auteur_nom = serializers.SerializerMethodField()

    class Meta:
        model = CommentaireVariance
        fields = [
            'id', 'company', 'cycle', 'departement', 'categorie', 'mois',
            'auteur', 'auteur_nom', 'texte', 'cree_le',
        ]
        read_only_fields = ['id', 'company', 'auteur', 'auteur_nom', 'cree_le']

    def get_auteur_nom(self, obj):
        if obj.auteur_id:
            return (getattr(obj.auteur, 'get_full_name', lambda: '')()
                    or obj.auteur.username)
        return ''


class MappingCategorieCompteSerializer(serializers.ModelSerializer):
    class Meta:
        model = MappingCategorieCompte
        fields = [
            'id', 'company', 'categorie', 'compte_cgnc_prefixe',
            'compte_cgnc_libelle',
        ]
        read_only_fields = ['id', 'company']
