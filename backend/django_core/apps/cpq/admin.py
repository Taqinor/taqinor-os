from django.contrib import admin

from .models import (
    OptionProduit, ContrainteCompatibilite, RegleProduitCPQ,
    OffreGroupee, LigneOffreGroupee, PrixContractuel, SeuilMargeFamille,
    RegleApprobationRemise, EtapeApprobationDevis,
    QuestionConfigurateur, SessionConfigurateur, ReponseConfigurateur,
)


@admin.register(OptionProduit)
class OptionProduitAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'produit', 'groupe_option', 'obligatoire')
    list_filter = ('company', 'obligatoire')


@admin.register(ContrainteCompatibilite)
class ContrainteCompatibiliteAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'produit_a', 'produit_b', 'type')
    list_filter = ('company', 'type')


@admin.register(RegleProduitCPQ)
class RegleProduitCPQAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'nom', 'actif', 'date_creation')
    list_filter = ('company', 'actif')


class LigneOffreGroupeeInline(admin.TabularInline):
    model = LigneOffreGroupee
    extra = 0


@admin.register(OffreGroupee)
class OffreGroupeeAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'nom', 'prix_total', 'actif')
    list_filter = ('company', 'actif')
    inlines = [LigneOffreGroupeeInline]


@admin.register(PrixContractuel)
class PrixContractuelAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'client', 'produit', 'prix_ht',
                    'date_debut', 'date_fin')
    list_filter = ('company',)


@admin.register(SeuilMargeFamille)
class SeuilMargeFamilleAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'categorie', 'marge_min_pct')
    list_filter = ('company',)


@admin.register(RegleApprobationRemise)
class RegleApprobationRemiseAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'libelle', 'remise_min_pct',
                    'remise_max_pct', 'nombre_approbateurs', 'actif')
    list_filter = ('company', 'actif')


@admin.register(EtapeApprobationDevis)
class EtapeApprobationDevisAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'devis', 'niveau', 'statut',
                    'approbateur')
    list_filter = ('company', 'statut')


@admin.register(QuestionConfigurateur)
class QuestionConfigurateurAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'ordre', 'texte', 'type', 'actif')
    list_filter = ('company', 'actif', 'type')


@admin.register(SessionConfigurateur)
class SessionConfigurateurAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'token', 'devis', 'created_at')
    list_filter = ('company',)


@admin.register(ReponseConfigurateur)
class ReponseConfigurateurAdmin(admin.ModelAdmin):
    list_display = ('id', 'session', 'question', 'valeur')
