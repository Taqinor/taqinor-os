from decimal import Decimal

from django.contrib import admin
from django.core.exceptions import PermissionDenied, ValidationError
from django.forms.models import BaseInlineFormSet

from core.admin_scoping import CompanyScopedAdminMixin

from .models import (
    AvancementRevenu, BaremeIndemnite, BordereauRemise, Budget, BudgetLigne,
    Caisse, CautionBancaire, CentreCout, ClotureCaisse, CommissionPayoutLine,
    CommissionPayoutRun, CompteComptable, CompteTresorerie, ContratAvancement,
    DeclarationTVA, EcritureComptable, Effet, EntiteConsolidation,
    ExerciceComptable, Immobilisation, IndemniteChantier, Journal,
    LigneEcriture, LignePrevisionnelTresorerie, LigneReleve, MouvementCaisse,
    NoteFrais, PaymentRun, PaymentRunLine, PeriodeComptable, PlanComptable,
    ProvisionCreance, Rapprochement, RapprochementBancaire, RetenueGarantie,
    RetenueSource, TimbreFiscal, TravauxEnCours, VirementInterne,
)


# ── AUD185 (F10) — scope société de TOUTE l'administration comptable ────────
# Aucun `admin.py` du dépôt ne surchargeait `get_queryset` : un compte
# `is_staff` d'une société listait les écritures, comptes de trésorerie et
# journaux de toutes les autres. Base commune posée ici, PARTAGÉE avec
# `apps/ventes/admin.py` (et `apps/stock/admin.py`, AUD215) via `core`.
class CompanyScopedAdmin(CompanyScopedAdminMixin, admin.ModelAdmin):
    """`ModelAdmin` dont la liste est bornée à `request.user.company`."""


# Messages (français) des deux verrous d'intégrité de la piste comptable.
SUPPRESSION_ECRITURE_VALIDEE_INTERDITE = (
    "Suppression refusée : cette écriture est VALIDÉE. Une pièce comptable "
    "validée fait partie de la piste d'audit — contre-passez-la (extourne) "
    "au lieu de la supprimer."
)
ECRITURE_DESEQUILIBREE_INTERDITE = (
    "Écriture déséquilibrée : la somme des débits doit égaler la somme des "
    "crédits. La modification a été annulée."
)


@admin.register(PlanComptable)
class PlanComptableAdmin(CompanyScopedAdmin):
    list_display = ('code', 'libelle', 'company', 'actif')
    list_filter = ('actif',)
    search_fields = ('code', 'libelle')


@admin.register(CompteComptable)
class CompteComptableAdmin(CompanyScopedAdmin):
    list_display = ('numero', 'intitule', 'classe', 'company', 'est_tiers',
                    'lettrable', 'actif')
    list_filter = ('classe', 'est_tiers', 'lettrable', 'actif')
    search_fields = ('numero', 'intitule')


@admin.register(Journal)
class JournalAdmin(CompanyScopedAdmin):
    list_display = ('code', 'libelle', 'type_journal', 'company', 'actif')
    list_filter = ('type_journal', 'actif')
    search_fields = ('code', 'libelle')


# ── AUD185 (F4) — l'équilibre est revérifié APRÈS le formset enfant ────────
# `EcritureComptable.clean()` (models.py) s'exécute sur le formulaire PARENT,
# AVANT que le formset des lignes ne sauvegarde : il relit donc les lignes
# telles qu'elles étaient EN BASE. `LigneEcriture.clean()` (models.py), lui, ne
# regarde qu'une ligne isolée. Résultat : le chemin le plus court — MODIFIER un
# montant (1000 → 900) sur une écriture validée — passait sans un mot. Ce
# formset resomme les lignes RÉELLEMENT soumises (créations, modifications,
# suppressions comprises) et refuse le déséquilibre avant toute écriture en
# base.
class LigneEcritureInlineFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        debit = Decimal('0')
        credit = Decimal('0')
        lignes = 0
        for form in self.forms:
            cleaned = getattr(form, 'cleaned_data', None)
            if not cleaned or cleaned.get('DELETE'):
                continue
            debit += cleaned.get('debit') or Decimal('0')
            credit += cleaned.get('credit') or Decimal('0')
            lignes += 1
        # Tolère 0 ligne (écriture en cours de saisie) — même contrat que
        # `EcritureComptable.clean()`.
        if lignes and debit != credit:
            raise ValidationError(
                f"{ECRITURE_DESEQUILIBREE_INTERDITE} "
                f"(Σ débit {debit} ≠ Σ crédit {credit})")


class LigneEcritureInline(admin.TabularInline):
    model = LigneEcriture
    formset = LigneEcritureInlineFormSet
    extra = 0
    # AUD185 (F11) — `company` est un FK NOT NULL du modèle : l'omettre du
    # formulaire faisait lever une IntegrityError BRUTE à l'ajout d'une ligne.
    # Affiché en lecture seule et pré-rempli depuis l'écriture parente par
    # `EcritureComptableAdmin.save_formset` (jamais saisi à la main : une ligne
    # ne peut pas appartenir à une autre société que son écriture).
    fields = ('company', 'compte', 'libelle', 'debit', 'credit', 'lettrage')
    readonly_fields = ('company',)


@admin.register(EcritureComptable)
class EcritureComptableAdmin(CompanyScopedAdmin):
    list_display = ('id', 'journal', 'date_ecriture', 'libelle', 'reference',
                    'statut', 'company')
    list_filter = ('statut', 'journal__type_journal')
    search_fields = ('libelle', 'reference')
    inlines = [LigneEcritureInline]
    # AUD185 (F8) — séparation des tâches COMPTA40 : seul
    # `services.valider_ecriture` pose ces trois champs (il refuse notamment
    # que le saisisseur se valide lui-même). Les laisser en écriture libre
    # dans /admin/ contournait tout le second regard.
    readonly_fields = ('statut', 'valide_par', 'date_validation')

    def save_formset(self, request, form, formset, change):
        """Pré-remplit `company` (F11) puis REVÉRIFIE l'équilibre (F4).

        Le contrôle d'équilibre principal vit dans
        `LigneEcritureInlineFormSet.clean()` (refus lisible, rien n'est écrit).
        Celui-ci est le verrou de dernier recours, posé APRÈS la sauvegarde des
        lignes : l'admin enveloppe tout le POST dans une transaction, donc
        lever ici annule l'ensemble.
        """
        if formset.model is not LigneEcriture:
            super().save_formset(request, form, formset, change)
            return
        instances = formset.save(commit=False)
        for obsolete in formset.deleted_objects:
            obsolete.delete()
        for instance in instances:
            if instance.company_id is None:
                instance.company = form.instance.company
            instance.save()
        formset.save_m2m()
        lignes = list(LigneEcriture.objects.filter(ecriture=form.instance))
        if not lignes:
            return
        debit = sum((lig.debit for lig in lignes), Decimal('0'))
        credit = sum((lig.credit for lig in lignes), Decimal('0'))
        if debit != credit:
            raise PermissionDenied(ECRITURE_DESEQUILIBREE_INTERDITE)

    # ── Garde anti-suppression d'une pièce validée ─────────────────────────
    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.statut == EcritureComptable.Statut.VALIDEE:
            return False
        return super().has_delete_permission(request, obj)

    def delete_model(self, request, obj):
        if obj.statut == EcritureComptable.Statut.VALIDEE:
            raise PermissionDenied(SUPPRESSION_ECRITURE_VALIDEE_INTERDITE)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        if queryset.filter(
                statut=EcritureComptable.Statut.VALIDEE).exists():
            raise PermissionDenied(SUPPRESSION_ECRITURE_VALIDEE_INTERDITE)
        super().delete_queryset(request, queryset)


@admin.register(CompteTresorerie)
class CompteTresorerieAdmin(CompanyScopedAdmin):
    list_display = ('libelle', 'type_compte', 'banque', 'devise', 'company',
                    'actif')
    list_filter = ('type_compte', 'actif')
    # AUD185 (F10) — `rib`/`iban` retirés de la recherche : une coordonnée
    # bancaire ne se cherche pas depuis une barre de recherche d'admin (elle
    # transite en clair dans l'URL et les journaux d'accès). Le libellé et la
    # banque suffisent pour retrouver un compte.
    search_fields = ('libelle', 'banque')


@admin.register(ExerciceComptable)
class ExerciceComptableAdmin(CompanyScopedAdmin):
    list_display = ('id', 'libelle', 'date_debut', 'date_fin', 'statut',
                    'an_reporte', 'company')
    list_filter = ('statut', 'an_reporte')
    search_fields = ('libelle',)


@admin.register(PeriodeComptable)
class PeriodeComptableAdmin(CompanyScopedAdmin):
    list_display = ('id', 'libelle', 'type_periode', 'date_debut', 'date_fin',
                    'verrouillee', 'company')
    list_filter = ('type_periode', 'verrouillee')
    search_fields = ('libelle',)
    # AUD185 (F9) — le verrou de période est le socle de l'immutabilité
    # (FG115) : seuls `services.verrouiller_periode` / `rouvrir_periode` le
    # posent, et c'est `rouvrir_periode` qui refuse la réouverture d'une
    # période appartenant à un exercice CLÔTURÉ. Trois cases à cocher dans
    # /admin/ contournaient ce garde.
    readonly_fields = ('verrouillee', 'date_verrouillage', 'verrouillee_par')


@admin.register(Immobilisation)
class ImmobilisationAdmin(CompanyScopedAdmin):
    list_display = ('id', 'libelle', 'categorie', 'cout', 'taux_tva',
                    'date_acquisition', 'company', 'actif')
    list_filter = ('categorie', 'actif')
    search_fields = ('libelle', 'reference')


class LigneReleveInline(admin.TabularInline):
    model = LigneReleve
    extra = 0
    fields = ('date_operation', 'libelle', 'reference', 'montant', 'statut')


@admin.register(RapprochementBancaire)
class RapprochementBancaireAdmin(CompanyScopedAdmin):
    list_display = ('id', 'compte_tresorerie', 'date_debut', 'date_fin',
                    'solde_releve', 'statut', 'company')
    list_filter = ('statut',)
    search_fields = ('libelle',)
    inlines = [LigneReleveInline]


@admin.register(LigneReleve)
class LigneReleveAdmin(CompanyScopedAdmin):
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
class CaisseAdmin(CompanyScopedAdmin):
    list_display = ('id', 'libelle', 'compte_tresorerie', 'solde_initial',
                    'actif', 'company')
    list_filter = ('actif',)
    search_fields = ('libelle',)
    inlines = [MouvementCaisseInline]


@admin.register(MouvementCaisse)
class MouvementCaisseAdmin(CompanyScopedAdmin):
    list_display = ('id', 'caisse', 'date_mouvement', 'sens', 'montant',
                    'motif', 'posted', 'company')
    list_filter = ('sens', 'posted')
    search_fields = ('motif', 'justificatif')


@admin.register(ClotureCaisse)
class ClotureCaisseAdmin(CompanyScopedAdmin):
    list_display = ('id', 'caisse', 'date_cloture', 'solde_theorique',
                    'solde_compte', 'ecart', 'company')
    search_fields = ('commentaire',)


@admin.register(VirementInterne)
class VirementInterneAdmin(CompanyScopedAdmin):
    list_display = ('id', 'compte_source', 'compte_destination', 'montant',
                    'date_virement', 'posted', 'company')
    list_filter = ('posted',)
    search_fields = ('libelle', 'reference')


@admin.register(LignePrevisionnelTresorerie)
class LignePrevisionnelTresorerieAdmin(CompanyScopedAdmin):
    list_display = ('id', 'libelle', 'categorie', 'date_prevue', 'montant',
                    'recurrence', 'company')
    list_filter = ('categorie', 'recurrence')
    search_fields = ('libelle', 'commentaire')


@admin.register(Effet)
class EffetAdmin(CompanyScopedAdmin):
    list_display = ('id', 'sens', 'type_effet', 'numero', 'montant',
                    'date_echeance', 'statut', 'company')
    list_filter = ('sens', 'type_effet', 'statut')
    search_fields = ('numero', 'tireur', 'banque')


@admin.register(BordereauRemise)
class BordereauRemiseAdmin(CompanyScopedAdmin):
    list_display = ('id', 'reference', 'compte_tresorerie', 'date_remise',
                    'total', 'statut', 'posted', 'company')
    list_filter = ('statut', 'posted')
    search_fields = ('reference',)


@admin.register(Rapprochement)
class RapprochementAdmin(CompanyScopedAdmin):
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
class PaymentRunAdmin(CompanyScopedAdmin):
    list_display = ('id', 'reference', 'mode_paiement', 'compte_tresorerie',
                    'date_paiement', 'total', 'statut', 'posted', 'company')
    list_filter = ('mode_paiement', 'statut', 'posted')
    search_fields = ('reference', 'note')
    inlines = [PaymentRunLineInline]


@admin.register(PaymentRunLine)
class PaymentRunLineAdmin(CompanyScopedAdmin):
    list_display = ('id', 'payment_run', 'beneficiaire', 'reference', 'montant',
                    'date_echeance', 'company')
    search_fields = ('beneficiaire', 'reference')


@admin.register(NoteFrais)
class NoteFraisAdmin(CompanyScopedAdmin):
    list_display = ('id', 'reference', 'employe', 'date_frais', 'categorie',
                    'montant', 'statut', 'date_remboursement', 'company')
    list_filter = ('statut', 'categorie', 'mode_remboursement')
    search_fields = ('reference', 'motif')


@admin.register(BaremeIndemnite)
class BaremeIndemniteAdmin(CompanyScopedAdmin):
    list_display = ('id', 'libelle', 'taux_km', 'per_diem', 'defaut', 'actif',
                    'company')
    list_filter = ('defaut', 'actif')
    search_fields = ('libelle',)


@admin.register(IndemniteChantier)
class IndemniteChantierAdmin(CompanyScopedAdmin):
    list_display = ('id', 'reference', 'employe', 'date_deplacement',
                    'libelle_chantier', 'distance_km', 'montant_total',
                    'statut', 'company')
    list_filter = ('statut', 'aller_retour')
    search_fields = ('reference', 'libelle_chantier')


@admin.register(DeclarationTVA)
class DeclarationTVAAdmin(CompanyScopedAdmin):
    list_display = ('id', 'reference', 'date_debut', 'date_fin', 'regime',
                    'methode', 'tva_collectee', 'tva_deductible',
                    'tva_a_declarer', 'statut', 'company')
    list_filter = ('regime', 'methode', 'statut')
    search_fields = ('reference', 'libelle')


@admin.register(RetenueSource)
class RetenueSourceAdmin(CompanyScopedAdmin):
    list_display = ('id', 'reference', 'date_piece', 'type_prestation',
                    'tiers_nom', 'base', 'taux', 'montant', 'statut', 'company')
    list_filter = ('type_prestation', 'statut')
    search_fields = ('reference', 'piece', 'tiers_nom', 'identifiant_fiscal')


@admin.register(TimbreFiscal)
class TimbreFiscalAdmin(CompanyScopedAdmin):
    list_display = ('id', 'reference', 'date_encaissement', 'facture_ref',
                    'tiers_nom', 'base', 'taux', 'minimum', 'montant', 'statut',
                    'company')
    list_filter = ('statut', 'mode_reglement')
    search_fields = ('reference', 'facture_ref', 'tiers_nom')


@admin.register(RetenueGarantie)
class RetenueGarantieAdmin(CompanyScopedAdmin):
    list_display = ('id', 'reference', 'marche_ref', 'tiers_nom', 'base',
                    'taux', 'montant', 'date_constitution', 'date_levee_prevue',
                    'statut', 'company')
    list_filter = ('statut',)
    search_fields = ('reference', 'marche_ref', 'facture_ref', 'tiers_nom')


@admin.register(CautionBancaire)
class CautionBancaireAdmin(CompanyScopedAdmin):
    list_display = ('id', 'reference', 'type_caution', 'marche_ref',
                    'tiers_nom', 'banque', 'montant', 'date_emission',
                    'date_echeance', 'statut', 'company')
    list_filter = ('type_caution', 'statut')
    search_fields = ('reference', 'marche_ref', 'tiers_nom', 'banque')


@admin.register(ContratAvancement)
class ContratAvancementAdmin(CompanyScopedAdmin):
    list_display = ('id', 'reference', 'libelle', 'chantier_ref', 'methode',
                    'revenu_total', 'cout_total_estime', 'statut', 'company')
    list_filter = ('methode', 'statut')
    search_fields = ('reference', 'libelle', 'chantier_ref', 'marche_ref',
                     'client_nom')


@admin.register(AvancementRevenu)
class AvancementRevenuAdmin(CompanyScopedAdmin):
    list_display = ('id', 'contrat', 'date_arrete', 'pourcentage',
                    'revenu_cumule', 'revenu_periode', 'ecriture_id', 'company')
    list_filter = ('date_arrete',)
    search_fields = ('contrat__reference',)


@admin.register(TravauxEnCours)
class TravauxEnCoursAdmin(CompanyScopedAdmin):
    list_display = ('id', 'reference', 'nature', 'libelle', 'montant',
                    'date_arrete', 'statut', 'company')
    list_filter = ('nature', 'statut')
    search_fields = ('reference', 'libelle', 'chantier_ref')


class CommissionPayoutLineInline(admin.TabularInline):
    model = CommissionPayoutLine
    extra = 0
    fields = ('commercial_nom', 'base', 'taux', 'montant', 'libelle')


@admin.register(CommissionPayoutRun)
class CommissionPayoutRunAdmin(CompanyScopedAdmin):
    list_display = ('id', 'reference', 'periode', 'date_run', 'statut',
                    'total', 'ecriture_id', 'company')
    list_filter = ('statut',)
    search_fields = ('reference', 'libelle', 'periode')
    inlines = [CommissionPayoutLineInline]


class BudgetLigneInline(admin.TabularInline):
    model = BudgetLigne
    extra = 0
    fields = ('compte', 'centre_cout', 'libelle')


@admin.register(Budget)
class BudgetAdmin(CompanyScopedAdmin):
    list_display = ('id', 'annee', 'libelle', 'statut', 'company')
    list_filter = ('annee', 'statut')
    search_fields = ('libelle',)
    inlines = [BudgetLigneInline]


@admin.register(CentreCout)
class CentreCoutAdmin(CompanyScopedAdmin):
    list_display = ('id', 'code', 'libelle', 'axe', 'actif', 'company')
    list_filter = ('axe', 'actif')
    search_fields = ('code', 'libelle')


@admin.register(ProvisionCreance)
class ProvisionCreanceAdmin(CompanyScopedAdmin):
    list_display = ('id', 'reference', 'tiers_nom', 'base', 'taux',
                    'dotation', 'date_dotation', 'statut', 'company')
    list_filter = ('statut',)
    search_fields = ('reference', 'tiers_nom')


@admin.register(EntiteConsolidation)
class EntiteConsolidationAdmin(CompanyScopedAdmin):
    list_display = ('id', 'company', 'entite', 'pourcentage_interet',
                    'methode', 'actif')
    list_filter = ('methode', 'actif')
