from django.contrib import admin

from .models import (
    BonCommandeFournisseur, BordereauRemise, Caisse, ClotureCaisse,
    CompteComptable, CompteTresorerie, EcritureComptable, Effet,
    ExerciceComptable, FactureFournisseur, Immobilisation, Journal,
    LigneEcriture, LigneBonCommandeFournisseur, LigneFactureFournisseur,
    LignePrevisionnelTresorerie, LigneReleve, LigneReceptionMarchandise,
    MouvementCaisse, PeriodeComptable, PlanComptable, Rapprochement3Voies,
    RapprochementBancaire, ReceptionMarchandise, VirementInterne,
)


@admin.register(PlanComptable)
class PlanComptableAdmin(admin.ModelAdmin):
    list_display = ('code', 'libelle', 'company', 'actif')
    list_filter = ('actif',)
    search_fields = ('code', 'libelle')


@admin.register(CompteComptable)
class CompteComptableAdmin(admin.ModelAdmin):
    list_display = ('numero', 'intitule', 'classe', 'company', 'est_tiers',
                    'lettrable', 'actif')
    list_filter = ('classe', 'est_tiers', 'lettrable', 'actif')
    search_fields = ('numero', 'intitule')


@admin.register(Journal)
class JournalAdmin(admin.ModelAdmin):
    list_display = ('code', 'libelle', 'type_journal', 'company', 'actif')
    list_filter = ('type_journal', 'actif')
    search_fields = ('code', 'libelle')


class LigneEcritureInline(admin.TabularInline):
    model = LigneEcriture
    extra = 0
    fields = ('compte', 'libelle', 'debit', 'credit', 'lettrage')


@admin.register(EcritureComptable)
class EcritureComptableAdmin(admin.ModelAdmin):
    list_display = ('id', 'journal', 'date_ecriture', 'libelle', 'reference',
                    'statut', 'company')
    list_filter = ('statut', 'journal__type_journal')
    search_fields = ('libelle', 'reference')
    inlines = [LigneEcritureInline]


@admin.register(CompteTresorerie)
class CompteTresorerieAdmin(admin.ModelAdmin):
    list_display = ('libelle', 'type_compte', 'banque', 'devise', 'company',
                    'actif')
    list_filter = ('type_compte', 'actif')
    search_fields = ('libelle', 'banque', 'rib', 'iban')


@admin.register(ExerciceComptable)
class ExerciceComptableAdmin(admin.ModelAdmin):
    list_display = ('id', 'libelle', 'date_debut', 'date_fin', 'statut',
                    'an_reporte', 'company')
    list_filter = ('statut', 'an_reporte')
    search_fields = ('libelle',)


@admin.register(PeriodeComptable)
class PeriodeComptableAdmin(admin.ModelAdmin):
    list_display = ('id', 'libelle', 'type_periode', 'date_debut', 'date_fin',
                    'verrouillee', 'company')
    list_filter = ('type_periode', 'verrouillee')
    search_fields = ('libelle',)


@admin.register(Immobilisation)
class ImmobilisationAdmin(admin.ModelAdmin):
    list_display = ('id', 'libelle', 'categorie', 'cout', 'taux_tva',
                    'date_acquisition', 'company', 'actif')
    list_filter = ('categorie', 'actif')
    search_fields = ('libelle', 'reference')


class LigneReleveInline(admin.TabularInline):
    model = LigneReleve
    extra = 0
    fields = ('date_operation', 'libelle', 'reference', 'montant', 'statut')


@admin.register(RapprochementBancaire)
class RapprochementBancaireAdmin(admin.ModelAdmin):
    list_display = ('id', 'compte_tresorerie', 'date_debut', 'date_fin',
                    'solde_releve', 'statut', 'company')
    list_filter = ('statut',)
    search_fields = ('libelle',)
    inlines = [LigneReleveInline]


@admin.register(LigneReleve)
class LigneReleveAdmin(admin.ModelAdmin):
    list_display = ('id', 'rapprochement', 'date_operation', 'libelle',
                    'montant', 'statut', 'company')
    list_filter = ('statut',)
    search_fields = ('libelle', 'reference')


class MouvementCaisseInline(admin.TabularInline):
    model = MouvementCaisse
    extra = 0
    fields = ('date_mouvement', 'sens', 'montant', 'motif', 'justificatif',
              'posted')


@admin.register(Caisse)
class CaisseAdmin(admin.ModelAdmin):
    list_display = ('id', 'libelle', 'compte_tresorerie', 'solde_initial',
                    'actif', 'company')
    list_filter = ('actif',)
    search_fields = ('libelle',)
    inlines = [MouvementCaisseInline]


@admin.register(MouvementCaisse)
class MouvementCaisseAdmin(admin.ModelAdmin):
    list_display = ('id', 'caisse', 'date_mouvement', 'sens', 'montant',
                    'motif', 'posted', 'company')
    list_filter = ('sens', 'posted')
    search_fields = ('motif', 'justificatif')


@admin.register(ClotureCaisse)
class ClotureCaisseAdmin(admin.ModelAdmin):
    list_display = ('id', 'caisse', 'date_cloture', 'solde_theorique',
                    'solde_compte', 'ecart', 'company')
    search_fields = ('commentaire',)


@admin.register(VirementInterne)
class VirementInterneAdmin(admin.ModelAdmin):
    list_display = ('id', 'compte_source', 'compte_destination', 'montant',
                    'date_virement', 'posted', 'company')
    list_filter = ('posted',)
    search_fields = ('libelle', 'reference')


@admin.register(LignePrevisionnelTresorerie)
class LignePrevisionnelTresorerieAdmin(admin.ModelAdmin):
    list_display = ('id', 'libelle', 'categorie', 'date_prevue', 'montant',
                    'recurrence', 'company')
    list_filter = ('categorie', 'recurrence')
    search_fields = ('libelle', 'commentaire')


@admin.register(Effet)
class EffetAdmin(admin.ModelAdmin):
    list_display = ('id', 'sens', 'type_effet', 'numero', 'montant',
                    'date_echeance', 'statut', 'company')
    list_filter = ('sens', 'type_effet', 'statut')
    search_fields = ('numero', 'tireur', 'banque')


@admin.register(BordereauRemise)
class BordereauRemiseAdmin(admin.ModelAdmin):
    list_display = ('id', 'reference', 'compte_tresorerie', 'date_remise',
                    'total', 'statut', 'posted', 'company')
    list_filter = ('statut', 'posted')
    search_fields = ('reference',)


# ── FG131 — Rapprochement 3 voies ──────────────────────────────────────────

class LigneBonCommandeFournisseurInline(admin.TabularInline):
    model = LigneBonCommandeFournisseur
    extra = 0
    fields = ('designation', 'quantite', 'prix_unitaire_ht', 'unite')


@admin.register(BonCommandeFournisseur)
class BonCommandeFournisseurAdmin(admin.ModelAdmin):
    list_display = ('id', 'reference', 'fournisseur_nom', 'date_commande',
                    'montant_ht', 'statut', 'company')
    list_filter = ('statut',)
    search_fields = ('reference', 'fournisseur_nom')
    inlines = [LigneBonCommandeFournisseurInline]


class LigneReceptionMarchandiseInline(admin.TabularInline):
    model = LigneReceptionMarchandise
    extra = 0
    fields = ('ligne_bc', 'quantite_recue', 'notes')


@admin.register(ReceptionMarchandise)
class ReceptionMarchandiseAdmin(admin.ModelAdmin):
    list_display = ('id', 'reference', 'bon_commande', 'date_reception',
                    'statut', 'company')
    list_filter = ('statut',)
    search_fields = ('reference', 'numero_bl_fournisseur')
    inlines = [LigneReceptionMarchandiseInline]


class LigneFactureFournisseurInline(admin.TabularInline):
    model = LigneFactureFournisseur
    extra = 0
    fields = ('designation', 'quantite_facturee', 'prix_unitaire_ht', 'unite',
              'ligne_bc')


@admin.register(FactureFournisseur)
class FactureFournisseurAdmin(admin.ModelAdmin):
    list_display = ('id', 'reference', 'fournisseur_nom', 'date_facture',
                    'montant_ht', 'montant_ttc', 'statut', 'company')
    list_filter = ('statut',)
    search_fields = ('reference', 'fournisseur_nom')
    inlines = [LigneFactureFournisseurInline]


@admin.register(Rapprochement3Voies)
class Rapprochement3VoiesAdmin(admin.ModelAdmin):
    list_display = ('id', 'bon_commande', 'reception', 'facture',
                    'montant_commande_ht', 'montant_recu_ht',
                    'montant_facture_ht', 'statut', 'company')
    list_filter = ('statut',)
    search_fields = ('libelle',)
    readonly_fields = (
        'montant_commande_ht', 'montant_recu_ht', 'montant_facture_ht',
        'ecart_commande_facture_ht', 'ecart_recu_facture_ht',
        'valide_par', 'date_validation',
    )
