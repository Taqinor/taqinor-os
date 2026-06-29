from django.contrib import admin

from .models import (
    BaremeIndemnite, BordereauRemise, Caisse, ClotureCaisse, CompteComptable,
    CompteTresorerie, DeclarationTVA, EcritureComptable, Effet,
    ExerciceComptable, Immobilisation, IndemniteChantier, Journal,
    LigneEcriture, LignePrevisionnelTresorerie, LigneReleve, MouvementCaisse,
    NoteFrais, PaymentRun, PaymentRunLine, PeriodeComptable, PlanComptable,
    Rapprochement, RapprochementBancaire, RetenueSource, TimbreFiscal,
    VirementInterne,
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


@admin.register(Rapprochement)
class RapprochementAdmin(admin.ModelAdmin):
    list_display = ('id', 'bon_commande', 'statut', 'montant_commande',
                    'montant_recu', 'montant_facture', 'ecart',
                    'date_evaluation', 'company')
    list_filter = ('statut',)
    search_fields = ('bon_commande__reference', 'note')


class PaymentRunLineInline(admin.TabularInline):
    model = PaymentRunLine
    extra = 0
    fields = ('beneficiaire', 'tiers_id', 'reference', 'montant',
              'date_echeance', 'rib', 'iban')


@admin.register(PaymentRun)
class PaymentRunAdmin(admin.ModelAdmin):
    list_display = ('id', 'reference', 'mode_paiement', 'compte_tresorerie',
                    'date_paiement', 'total', 'statut', 'posted', 'company')
    list_filter = ('mode_paiement', 'statut', 'posted')
    search_fields = ('reference', 'note')
    inlines = [PaymentRunLineInline]


@admin.register(PaymentRunLine)
class PaymentRunLineAdmin(admin.ModelAdmin):
    list_display = ('id', 'payment_run', 'beneficiaire', 'reference', 'montant',
                    'date_echeance', 'company')
    search_fields = ('beneficiaire', 'reference')


@admin.register(NoteFrais)
class NoteFraisAdmin(admin.ModelAdmin):
    list_display = ('id', 'reference', 'employe', 'date_frais', 'categorie',
                    'montant', 'statut', 'date_remboursement', 'company')
    list_filter = ('statut', 'categorie', 'mode_remboursement')
    search_fields = ('reference', 'motif')


@admin.register(BaremeIndemnite)
class BaremeIndemniteAdmin(admin.ModelAdmin):
    list_display = ('id', 'libelle', 'taux_km', 'per_diem', 'defaut', 'actif',
                    'company')
    list_filter = ('defaut', 'actif')
    search_fields = ('libelle',)


@admin.register(IndemniteChantier)
class IndemniteChantierAdmin(admin.ModelAdmin):
    list_display = ('id', 'reference', 'employe', 'date_deplacement',
                    'libelle_chantier', 'distance_km', 'montant_total',
                    'statut', 'company')
    list_filter = ('statut', 'aller_retour')
    search_fields = ('reference', 'libelle_chantier')


@admin.register(DeclarationTVA)
class DeclarationTVAAdmin(admin.ModelAdmin):
    list_display = ('id', 'reference', 'date_debut', 'date_fin', 'regime',
                    'methode', 'tva_collectee', 'tva_deductible',
                    'tva_a_declarer', 'statut', 'company')
    list_filter = ('regime', 'methode', 'statut')
    search_fields = ('reference', 'libelle')


@admin.register(RetenueSource)
class RetenueSourceAdmin(admin.ModelAdmin):
    list_display = ('id', 'reference', 'date_piece', 'type_prestation',
                    'tiers_nom', 'base', 'taux', 'montant', 'statut', 'company')
    list_filter = ('type_prestation', 'statut')
    search_fields = ('reference', 'piece', 'tiers_nom', 'identifiant_fiscal')


@admin.register(TimbreFiscal)
class TimbreFiscalAdmin(admin.ModelAdmin):
    list_display = ('id', 'reference', 'date_encaissement', 'facture_ref',
                    'tiers_nom', 'base', 'taux', 'minimum', 'montant', 'statut',
                    'company')
    list_filter = ('statut', 'mode_reglement')
    search_fields = ('reference', 'facture_ref', 'tiers_nom')
