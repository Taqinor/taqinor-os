from django.contrib import admin

from .models import (
    AccidentTravail,
    AffectationRoster,
    Certification,
    Competence,
    CompetenceEmploye,
    DemandeConge,
    Departement,
    DocumentEmploye,
    DossierEmploye,
    DotationEpi,
    ElementSortie,
    EmargementEpi,
    EpiCatalogue,
    Habilitation,
    HeuresSupp,
    IncidentPresence,
    Pointage,
    Poste,
    PresenceChantier,
    Remuneration,
    SoldeConge,
    TypeAbsence,
    VisiteMedicale,
)


@admin.register(Departement)
class DepartementAdmin(admin.ModelAdmin):
    list_display = ('nom', 'code', 'company', 'actif')
    list_filter = ('actif',)
    search_fields = ('nom', 'code')


@admin.register(Remuneration)
class RemunerationAdmin(admin.ModelAdmin):
    list_display = ('employe', 'montant', 'devise', 'periodicite',
                    'date_effet', 'company')
    list_filter = ('periodicite', 'devise')
    search_fields = ('employe__matricule', 'employe__nom', 'employe__prenom')


@admin.register(DossierEmploye)
class DossierEmployeAdmin(admin.ModelAdmin):
    list_display = ('matricule', 'nom', 'prenom', 'poste', 'departement',
                    'type_contrat', 'contrat_date_fin', 'statut', 'company')
    list_filter = ('type_contrat', 'statut', 'departement')
    search_fields = ('matricule', 'nom', 'prenom', 'cin', 'email')


@admin.register(DocumentEmploye)
class DocumentEmployeAdmin(admin.ModelAdmin):
    list_display = ('employe', 'type_document', 'date_expiration',
                    'date_creation', 'company')
    list_filter = ('type_document',)
    search_fields = ('employe__matricule', 'employe__nom', 'employe__prenom')


@admin.register(Poste)
class PosteAdmin(admin.ModelAdmin):
    list_display = ('intitule', 'code', 'departement', 'actif', 'company')
    list_filter = ('actif',)
    search_fields = ('intitule', 'code')


@admin.register(ElementSortie)
class ElementSortieAdmin(admin.ModelAdmin):
    list_display = ('employe', 'libelle', 'type_element', 'recupere',
                    'date_recuperation', 'company')
    list_filter = ('type_element', 'recupere')
    search_fields = ('employe__matricule', 'employe__nom', 'libelle')


@admin.register(TypeAbsence)
class TypeAbsenceAdmin(admin.ModelAdmin):
    list_display = ('code', 'libelle', 'decompte_jours_ouvres', 'deduit_solde',
                    'remunere', 'actif', 'company')
    list_filter = ('decompte_jours_ouvres', 'deduit_solde', 'remunere', 'actif')
    search_fields = ('code', 'libelle')


@admin.register(SoldeConge)
class SoldeCongeAdmin(admin.ModelAdmin):
    list_display = ('employe', 'annee', 'acquis', 'report', 'pris', 'company')
    list_filter = ('annee',)
    search_fields = ('employe__matricule', 'employe__nom', 'employe__prenom')


@admin.register(DemandeConge)
class DemandeCongeAdmin(admin.ModelAdmin):
    list_display = ('employe', 'type_absence', 'date_debut', 'date_fin',
                    'jours', 'statut', 'company')
    list_filter = ('statut', 'type_absence')
    search_fields = ('employe__matricule', 'employe__nom', 'employe__prenom')


@admin.register(Pointage)
class PointageAdmin(admin.ModelAdmin):
    list_display = ('employe', 'type_pointage', 'heure_arrivee', 'heure_depart',
                    'company', 'date_creation')
    list_filter = ('type_pointage',)
    search_fields = ('employe__matricule', 'employe__nom', 'employe__prenom')


@admin.register(HeuresSupp)
class HeuresSuppAdmin(admin.ModelAdmin):
    list_display = ('employe', 'date', 'heures_travaillees', 'hs_25', 'hs_50',
                    'hs_100', 'jour_repos_ferie', 'company')
    list_filter = ('jour_repos_ferie',)
    search_fields = ('employe__matricule', 'employe__nom', 'employe__prenom')


@admin.register(AffectationRoster)
class AffectationRosterAdmin(admin.ModelAdmin):
    list_display = ('employe', 'equipe', 'date', 'creneau', 'vehicule_id',
                    'conflit_conge', 'company')
    list_filter = ('creneau', 'conflit_conge')
    search_fields = ('employe__matricule', 'employe__nom', 'equipe')


@admin.register(PresenceChantier)
class PresenceChantierAdmin(admin.ModelAdmin):
    list_display = ('employe', 'installation_id', 'date', 'statut', 'emarge',
                    'company')
    list_filter = ('statut', 'emarge')
    search_fields = ('employe__matricule', 'employe__nom', 'employe__prenom')


@admin.register(IncidentPresence)
class IncidentPresenceAdmin(admin.ModelAdmin):
    list_display = ('employe', 'type_incident', 'date', 'minutes_retard',
                    'justifie', 'company')
    list_filter = ('type_incident', 'justifie')
    search_fields = ('employe__matricule', 'employe__nom', 'employe__prenom')


@admin.register(Competence)
class CompetenceAdmin(admin.ModelAdmin):
    list_display = ('code', 'libelle', 'domaine', 'actif', 'company')
    list_filter = ('domaine', 'actif')
    search_fields = ('code', 'libelle', 'description')


@admin.register(CompetenceEmploye)
class CompetenceEmployeAdmin(admin.ModelAdmin):
    list_display = ('employe', 'competence', 'niveau', 'evalue_le', 'company')
    list_filter = ('niveau', 'competence__domaine')
    search_fields = ('employe__matricule', 'employe__nom',
                     'competence__code', 'competence__libelle')


@admin.register(Habilitation)
class HabilitationAdmin(admin.ModelAdmin):
    list_display = ('employe', 'type_habilitation', 'organisme',
                    'date_obtention', 'date_validite', 'actif', 'company')
    list_filter = ('type_habilitation', 'actif')
    search_fields = ('employe__matricule', 'employe__nom', 'employe__prenom',
                     'organisme')


@admin.register(Certification)
class CertificationAdmin(admin.ModelAdmin):
    list_display = ('employe', 'type_certification', 'organisme',
                    'date_obtention', 'date_validite', 'actif', 'company')
    list_filter = ('type_certification', 'actif')
    search_fields = ('employe__matricule', 'employe__nom', 'employe__prenom',
                     'organisme')


@admin.register(VisiteMedicale)
class VisiteMedicaleAdmin(admin.ModelAdmin):
    list_display = ('employe', 'aptitude', 'date_visite', 'prochaine_visite',
                    'medecin', 'organisme', 'actif', 'company')
    list_filter = ('aptitude', 'actif')
    search_fields = ('employe__matricule', 'employe__nom', 'employe__prenom',
                     'medecin', 'organisme')


@admin.register(EpiCatalogue)
class EpiCatalogueAdmin(admin.ModelAdmin):
    list_display = ('designation', 'type_epi', 'actif', 'company')
    list_filter = ('type_epi', 'actif')
    search_fields = ('designation',)


@admin.register(DotationEpi)
class DotationEpiAdmin(admin.ModelAdmin):
    list_display = ('employe', 'epi', 'taille', 'date_dotation',
                    'date_renouvellement', 'quantite', 'accuse_remise',
                    'company')
    list_filter = ('epi__type_epi', 'accuse_remise')
    search_fields = ('employe__matricule', 'employe__nom', 'employe__prenom',
                     'epi__designation', 'taille')


@admin.register(EmargementEpi)
class EmargementEpiAdmin(admin.ModelAdmin):
    list_display = ('signataire_nom', 'dotation', 'role_signataire',
                    'methode', 'date_signature', 'company')
    list_filter = ('role_signataire', 'methode')
    search_fields = ('signataire_nom', 'dotation__employe__matricule',
                     'dotation__epi__designation')


@admin.register(AccidentTravail)
class AccidentTravailAdmin(admin.ModelAdmin):
    list_display = ('reference', 'employe', 'date_accident', 'gravite',
                    'arret_travail', 'nb_jours_arret', 'declare_cnss',
                    'statut', 'company')
    list_filter = ('gravite', 'statut', 'arret_travail', 'declare_cnss')
    search_fields = ('reference', 'lieu', 'employe__matricule',
                     'employe__nom', 'employe__prenom')
