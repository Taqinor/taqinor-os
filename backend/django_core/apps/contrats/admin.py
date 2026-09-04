from django.contrib import admin

from core.admin_scoping import CompanyScopedAdminMixin

from .models import (
    AlerteContrat,
    Caution,
    ClauseContrat,
    Contrat,
    ContratActivity,
    ContratLien,
    EcheancierContrat,
    EngagementSLA,
    EtapeApprobation,
    IndexationPrix,
    JalonContrat,
    LigneEcheance,
    Obligation,
    PartieContrat,
    PieceConformite,
    RegleApprobation,
    RetenueGarantie,
    SignatureContrat,
    VersionContrat,
)


# ── AUD417 — scope société de TOUTE l'administration de ce module ───────────
# Extension du mixin AUD185 (`core/admin_scoping.py`), déjà appliqué à
# ventes/compta : aucun `ModelAdmin` de ce fichier ne bornait sa liste à
# `request.user.company`, alors que ses modèles portent un FK `company`. Un
# superutilisateur RATTACHÉ À UNE SOCIÉTÉ y voyait — et cherchait par nom —
# les lignes de TOUTES les sociétés clientes simultanément. Le mixin est
# défensif : modèle sans FK `company`, ou compte sans société (opérateur
# plateforme), ⇒ aucun filtre, comportement historique inchangé.
class CompanyScopedAdmin(CompanyScopedAdminMixin, admin.ModelAdmin):
    """`ModelAdmin` dont la liste est bornée à `request.user.company`."""


@admin.register(Contrat)
class ContratAdmin(CompanyScopedAdmin):
    list_display = ('id', 'reference', 'objet', 'type_contrat', 'statut',
                    'confidentialite', 'montant', 'devise', 'company')
    list_filter = ('type_contrat', 'statut', 'confidentialite')
    search_fields = ('reference', 'objet')


@admin.register(PartieContrat)
class PartieContratAdmin(CompanyScopedAdmin):
    list_display = ('id', 'contrat', 'type_partie', 'nom', 'email',
                    'ordre', 'company')
    list_filter = ('type_partie',)
    search_fields = ('nom', 'email')


@admin.register(ContratLien)
class ContratLienAdmin(CompanyScopedAdmin):
    list_display = ('id', 'contrat', 'type_cible', 'cible_id', 'libelle',
                    'company')
    list_filter = ('type_cible',)
    search_fields = ('libelle',)


@admin.register(ClauseContrat)
class ClauseContratAdmin(CompanyScopedAdmin):
    list_display = ('id', 'contrat', 'clause', 'titre', 'ordre',
                    'surchargee', 'company')
    list_filter = ('surchargee',)
    search_fields = ('titre', 'corps')


@admin.register(RegleApprobation)
class RegleApprobationAdmin(CompanyScopedAdmin):
    list_display = ('id', 'libelle', 'type_contrat', 'montant_min',
                    'montant_max', 'niveau_approbation', 'nombre_approbateurs',
                    'priorite', 'actif', 'company')
    list_filter = ('type_contrat', 'niveau_approbation', 'actif')
    search_fields = ('libelle',)


@admin.register(EtapeApprobation)
class EtapeApprobationAdmin(CompanyScopedAdmin):
    list_display = ('id', 'contrat', 'niveau', 'niveau_approbation',
                    'statut', 'approbateur', 'decision_le', 'company')
    list_filter = ('statut', 'niveau_approbation')
    search_fields = ('commentaire',)


@admin.register(ContratActivity)
class ContratActivityAdmin(CompanyScopedAdmin):
    list_display = ('id', 'contrat', 'type', 'field', 'auteur',
                    'date_creation', 'company')
    list_filter = ('type', 'field')
    search_fields = ('message', 'old_value', 'new_value')


@admin.register(SignatureContrat)
class SignatureContratAdmin(CompanyScopedAdmin):
    list_display = ('id', 'contrat', 'role_signataire', 'signataire_nom',
                    'signataire', 'methode', 'date_signature', 'company')
    list_filter = ('role_signataire', 'methode')
    search_fields = ('signataire_nom',)


@admin.register(VersionContrat)
class VersionContratAdmin(CompanyScopedAdmin):
    list_display = ('id', 'contrat', 'version', 'motif', 'fichier_key',
                    'cree_par', 'cree_le', 'company')
    list_filter = ('version',)
    search_fields = ('motif', 'fichier_key')
    readonly_fields = ('version', 'cree_le')


@admin.register(AlerteContrat)
class AlerteContratAdmin(CompanyScopedAdmin):
    list_display = ('id', 'contrat', 'type_alerte', 'date_declenchement',
                    'statut', 'date_envoi', 'cree_par', 'company')
    list_filter = ('type_alerte', 'statut')
    search_fields = ('message',)
    readonly_fields = ('date_envoi', 'date_creation')


@admin.register(JalonContrat)
class JalonContratAdmin(CompanyScopedAdmin):
    list_display = ('id', 'contrat', 'numero', 'intitule', 'date_cible',
                    'statut', 'date_atteinte', 'company')
    list_filter = ('statut',)
    search_fields = ('intitule', 'description')
    readonly_fields = ('numero', 'date_creation')


@admin.register(Obligation)
class ObligationAdmin(CompanyScopedAdmin):
    list_display = ('id', 'contrat', 'jalon', 'intitule', 'redevable',
                    'date_echeance', 'statut', 'date_realisation', 'company')
    list_filter = ('statut', 'redevable')
    search_fields = ('intitule', 'description')
    readonly_fields = ('date_realisation', 'date_creation')


@admin.register(EngagementSLA)
class EngagementSLAAdmin(CompanyScopedAdmin):
    list_display = ('id', 'contrat', 'libelle', 'taux_cible', 'unite',
                    'mode_penalite', 'valeur_penalite', 'penalite_max',
                    'actif', 'company')
    list_filter = ('mode_penalite', 'actif')
    search_fields = ('libelle', 'unite')
    readonly_fields = ('date_creation',)


@admin.register(RetenueGarantie)
class RetenueGarantieAdmin(CompanyScopedAdmin):
    list_display = ('id', 'contrat', 'montant_base', 'taux', 'montant_retenu',
                    'date_retenue', 'date_liberation_prevue',
                    'date_liberation_effective', 'statut', 'company')
    list_filter = ('statut',)
    search_fields = ('note',)
    readonly_fields = ('montant_retenu', 'date_liberation_effective',
                       'date_creation')


@admin.register(Caution)
class CautionAdmin(CompanyScopedAdmin):
    list_display = ('id', 'contrat', 'type_caution', 'garant', 'reference',
                    'montant', 'devise', 'date_emission', 'date_expiration',
                    'statut', 'company')
    list_filter = ('type_caution', 'statut')
    search_fields = ('garant', 'reference', 'note')
    readonly_fields = ('date_creation',)


@admin.register(EcheancierContrat)
class EcheancierContratAdmin(CompanyScopedAdmin):
    list_display = ('id', 'contrat', 'libelle', 'periodicite',
                    'montant_total', 'devise', 'statut', 'facturation_active',
                    'company')
    list_filter = ('periodicite', 'statut', 'facturation_active')
    search_fields = ('libelle',)
    readonly_fields = ('montant_total', 'date_creation')


@admin.register(LigneEcheance)
class LigneEcheanceAdmin(CompanyScopedAdmin):
    list_display = ('id', 'echeancier', 'numero', 'libelle', 'date_echeance',
                    'montant', 'statut', 'date_paiement', 'facture_id',
                    'company')
    list_filter = ('statut',)
    search_fields = ('libelle',)
    readonly_fields = ('numero', 'date_paiement', 'facture_id',
                       'date_creation')


@admin.register(IndexationPrix)
class IndexationPrixAdmin(CompanyScopedAdmin):
    list_display = ('id', 'contrat', 'libelle', 'indice', 'valeur_base',
                    'part_fixe', 'periodicite', 'date_derniere_revision',
                    'actif', 'company')
    list_filter = ('periodicite', 'actif')
    search_fields = ('libelle', 'indice')
    readonly_fields = ('date_derniere_revision', 'date_creation')


@admin.register(PieceConformite)
class PieceConformiteAdmin(CompanyScopedAdmin):
    list_display = ('id', 'contrat', 'type_piece', 'libelle', 'obligatoire',
                    'statut', 'ged_document_id', 'date_fourniture',
                    'date_expiration', 'company')
    list_filter = ('type_piece', 'statut', 'obligatoire')
    search_fields = ('libelle', 'note')
    readonly_fields = ('date_fourniture', 'date_creation')
