from django.contrib import admin

from .models import (
    AlerteContrat,
    ClauseContrat,
    Contrat,
    ContratActivity,
    ContratLien,
    EtapeApprobation,
    PartieContrat,
    RegleApprobation,
    SignatureContrat,
    VersionContrat,
)


@admin.register(Contrat)
class ContratAdmin(admin.ModelAdmin):
    list_display = ('id', 'reference', 'objet', 'type_contrat', 'statut',
                    'confidentialite', 'montant', 'devise', 'company')
    list_filter = ('type_contrat', 'statut', 'confidentialite')
    search_fields = ('reference', 'objet')


@admin.register(PartieContrat)
class PartieContratAdmin(admin.ModelAdmin):
    list_display = ('id', 'contrat', 'type_partie', 'nom', 'email',
                    'ordre', 'company')
    list_filter = ('type_partie',)
    search_fields = ('nom', 'email')


@admin.register(ContratLien)
class ContratLienAdmin(admin.ModelAdmin):
    list_display = ('id', 'contrat', 'type_cible', 'cible_id', 'libelle',
                    'company')
    list_filter = ('type_cible',)
    search_fields = ('libelle',)


@admin.register(ClauseContrat)
class ClauseContratAdmin(admin.ModelAdmin):
    list_display = ('id', 'contrat', 'clause', 'titre', 'ordre',
                    'surchargee', 'company')
    list_filter = ('surchargee',)
    search_fields = ('titre', 'corps')


@admin.register(RegleApprobation)
class RegleApprobationAdmin(admin.ModelAdmin):
    list_display = ('id', 'libelle', 'type_contrat', 'montant_min',
                    'montant_max', 'niveau_approbation', 'nombre_approbateurs',
                    'priorite', 'actif', 'company')
    list_filter = ('type_contrat', 'niveau_approbation', 'actif')
    search_fields = ('libelle',)


@admin.register(EtapeApprobation)
class EtapeApprobationAdmin(admin.ModelAdmin):
    list_display = ('id', 'contrat', 'niveau', 'niveau_approbation',
                    'statut', 'approbateur', 'decision_le', 'company')
    list_filter = ('statut', 'niveau_approbation')
    search_fields = ('commentaire',)


@admin.register(ContratActivity)
class ContratActivityAdmin(admin.ModelAdmin):
    list_display = ('id', 'contrat', 'type', 'field', 'auteur',
                    'date_creation', 'company')
    list_filter = ('type', 'field')
    search_fields = ('message', 'old_value', 'new_value')


@admin.register(SignatureContrat)
class SignatureContratAdmin(admin.ModelAdmin):
    list_display = ('id', 'contrat', 'role_signataire', 'signataire_nom',
                    'signataire', 'methode', 'date_signature', 'company')
    list_filter = ('role_signataire', 'methode')
    search_fields = ('signataire_nom',)


@admin.register(VersionContrat)
class VersionContratAdmin(admin.ModelAdmin):
    list_display = ('id', 'contrat', 'version', 'motif', 'fichier_key',
                    'cree_par', 'cree_le', 'company')
    list_filter = ('version',)
    search_fields = ('motif', 'fichier_key')
    readonly_fields = ('version', 'cree_le')


@admin.register(AlerteContrat)
class AlerteContratAdmin(admin.ModelAdmin):
    list_display = ('id', 'contrat', 'type_alerte', 'date_declenchement',
                    'statut', 'date_envoi', 'cree_par', 'company')
    list_filter = ('type_alerte', 'statut')
    search_fields = ('message',)
    readonly_fields = ('date_envoi', 'date_creation')
