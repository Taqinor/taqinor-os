from django.contrib import admin

from .models import (
    ActionCorrectivePreventive, BilanCarbone, BordereauSuiviDechet,
    ConformiteEnvironnementale, ConsignationLoto,
    Dechet, EvaluationRisque,
    IndicateurESG,
    InspectionSecurite,
    LigneBilanCarbone,
    LigneEvaluationRisque,
    NonConformite, PermisTravail, PlanInspectionChantier,
    PlanInspectionModele, PointControleModele, ProcedureQualite,
    RecyclageModule,
    ReleveControle, ReleveCourbeIV, RetourClientQualite,
)


@admin.register(NonConformite)
class NonConformiteAdmin(admin.ModelAdmin):
    list_display = ('id', 'reference', 'titre', 'gravite', 'statut',
                    'company', 'date_detection')
    list_filter = ('gravite', 'statut')
    search_fields = ('reference', 'titre', 'origine')


@admin.register(ActionCorrectivePreventive)
class ActionCorrectivePreventiveAdmin(admin.ModelAdmin):
    list_display = ('id', 'non_conformite', 'type_action', 'statut',
                    'responsable', 'echeance', 'company')
    list_filter = ('type_action', 'statut')
    search_fields = ('description', 'cause_racine')


@admin.register(PlanInspectionModele)
class PlanInspectionModeleAdmin(admin.ModelAdmin):
    list_display = ('id', 'code', 'nom', 'actif', 'company', 'date_creation')
    list_filter = ('actif',)
    search_fields = ('code', 'nom', 'description')


@admin.register(PointControleModele)
class PointControleModeleAdmin(admin.ModelAdmin):
    list_display = ('id', 'plan', 'ordre', 'intitule', 'phase',
                    'type_releve', 'hold_point', 'company')
    list_filter = ('type_releve', 'hold_point')
    search_fields = ('intitule', 'phase', 'description')


@admin.register(PlanInspectionChantier)
class PlanInspectionChantierAdmin(admin.ModelAdmin):
    list_display = ('id', 'modele', 'chantier_id', 'statut',
                    'date_ouverture', 'company', 'date_creation')
    list_filter = ('statut',)
    search_fields = ('modele__nom', 'modele__code')


@admin.register(ReleveControle)
class ReleveControleAdmin(admin.ModelAdmin):
    list_display = ('id', 'plan_chantier', 'point', 'conforme',
                    'date_releve', 'releve_par', 'company')
    list_filter = ('conforme',)
    search_fields = ('valeur', 'point__intitule')


@admin.register(ReleveCourbeIV)
class ReleveCourbeIVAdmin(admin.ModelAdmin):
    list_display = ('id', 'string_id', 'chantier_id', 'voc', 'isc',
                    'pmpp', 'date_releve', 'releve_par', 'company')
    search_fields = ('string_id', 'notes')


@admin.register(ProcedureQualite)
class ProcedureQualiteAdmin(admin.ModelAdmin):
    list_display = ('id', 'reference', 'titre', 'version', 'statut',
                    'date_application', 'auteur', 'company', 'date_creation')
    list_filter = ('statut',)
    search_fields = ('reference', 'titre', 'contenu')


@admin.register(RetourClientQualite)
class RetourClientQualiteAdmin(admin.ModelAdmin):
    list_display = ('id', 'note_satisfaction', 'chantier_id', 'client_id',
                    'canal', 'traite', 'date_retour', 'company',
                    'date_creation')
    list_filter = ('traite', 'canal')
    search_fields = ('commentaire',)


@admin.register(EvaluationRisque)
class EvaluationRisqueAdmin(admin.ModelAdmin):
    list_display = ('id', 'reference', 'titre', 'statut', 'date_evaluation',
                    'chantier_id', 'evaluateur', 'company', 'date_creation')
    list_filter = ('statut',)
    search_fields = ('reference', 'titre', 'notes')


@admin.register(LigneEvaluationRisque)
class LigneEvaluationRisqueAdmin(admin.ModelAdmin):
    list_display = ('id', 'evaluation', 'poste', 'activite', 'danger',
                    'gravite', 'probabilite', 'criticite', 'company')
    list_filter = ('gravite', 'probabilite')
    search_fields = ('danger', 'poste', 'activite')


@admin.register(PermisTravail)
class PermisTravailAdmin(admin.ModelAdmin):
    list_display = ('id', 'reference', 'titre', 'type_permis', 'statut',
                    'chantier_id', 'date_debut', 'date_fin', 'company',
                    'date_creation')
    list_filter = ('type_permis', 'statut')
    search_fields = ('reference', 'titre', 'delivre_par__username',
                     'valide_par__username')


@admin.register(ConsignationLoto)
class ConsignationLotoAdmin(admin.ModelAdmin):
    list_display = ('id', 'reference', 'permis', 'equipement',
                    'point_consignation', 'consignateur', 'statut',
                    'verifie_absence_tension', 'date_consignation',
                    'date_deconsignation', 'company', 'date_creation')
    list_filter = ('statut', 'verifie_absence_tension')
    search_fields = ('reference', 'equipement', 'point_consignation',
                     'consignateur')


@admin.register(InspectionSecurite)
class InspectionSecuriteAdmin(admin.ModelAdmin):
    list_display = ('id', 'reference', 'titre', 'statut', 'resultat',
                    'chantier_id', 'date_prevue', 'date_realisee',
                    'inspecteur', 'ncr', 'company', 'date_creation')
    list_filter = ('statut', 'resultat')
    search_fields = ('reference', 'titre', 'observations')


@admin.register(Dechet)
class DechetAdmin(admin.ModelAdmin):
    list_display = ('id', 'libelle', 'code', 'categorie', 'mode_traitement',
                    'unite', 'actif', 'company', 'date_creation')
    list_filter = ('categorie', 'mode_traitement', 'actif')
    search_fields = ('libelle', 'code')


@admin.register(BordereauSuiviDechet)
class BordereauSuiviDechetAdmin(admin.ModelAdmin):
    list_display = ('id', 'reference', 'dechet', 'statut', 'chantier_id',
                    'quantite', 'date_emission', 'date_traitement',
                    'company', 'date_creation')
    list_filter = ('statut',)
    search_fields = ('reference', 'producteur', 'transporteur', 'eliminateur')


@admin.register(RecyclageModule)
class RecyclageModuleAdmin(admin.ModelAdmin):
    list_display = ('id', 'reference', 'marque', 'modele', 'nombre_modules',
                    'motif', 'statut', 'chantier_id', 'date_collecte',
                    'date_recyclage', 'company', 'date_creation')
    list_filter = ('motif', 'statut')
    search_fields = ('reference', 'marque', 'modele', 'filiere')


@admin.register(ConformiteEnvironnementale)
class ConformiteEnvironnementaleAdmin(admin.ModelAdmin):
    list_display = ('id', 'intitule', 'type_conformite', 'statut',
                    'autorite', 'date_expiration', 'prealerte_jours',
                    'responsable', 'company', 'date_creation')
    list_filter = ('type_conformite', 'statut')
    search_fields = ('intitule', 'autorite', 'reference_dossier')


@admin.register(BilanCarbone)
class BilanCarboneAdmin(admin.ModelAdmin):
    list_display = ('id', 'libelle', 'annee', 'statut', 'company',
                    'date_creation')
    list_filter = ('statut', 'annee')
    search_fields = ('libelle', 'perimetre')


@admin.register(LigneBilanCarbone)
class LigneBilanCarboneAdmin(admin.ModelAdmin):
    list_display = ('id', 'bilan', 'libelle', 'scope', 'categorie',
                    'quantite', 'unite', 'facteur_emission', 'company')
    list_filter = ('scope',)
    search_fields = ('libelle', 'categorie')


@admin.register(IndicateurESG)
class IndicateurESGAdmin(admin.ModelAdmin):
    list_display = ('id', 'code', 'libelle', 'pilier', 'valeur', 'cible',
                    'unite', 'annee', 'periode', 'company', 'date_creation')
    list_filter = ('pilier', 'annee')
    search_fields = ('code', 'libelle')
