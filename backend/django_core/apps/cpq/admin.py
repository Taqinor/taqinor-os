from django.contrib import admin

from core.admin_scoping import CompanyScopedAdminMixin

from .models import (
    OptionProduit, ContrainteCompatibilite, RegleProduitCPQ,
    OffreGroupee, LigneOffreGroupee, PrixContractuel, SeuilMargeFamille,
    RegleApprobationRemise, EtapeApprobationDevis,
    QuestionConfigurateur, SessionConfigurateur, ReponseConfigurateur,
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


@admin.register(OptionProduit)
class OptionProduitAdmin(CompanyScopedAdmin):
    list_display = ('id', 'company', 'produit', 'groupe_option', 'obligatoire')
    list_filter = ('company', 'obligatoire')


@admin.register(ContrainteCompatibilite)
class ContrainteCompatibiliteAdmin(CompanyScopedAdmin):
    list_display = ('id', 'company', 'produit_a', 'produit_b', 'type')
    list_filter = ('company', 'type')


@admin.register(RegleProduitCPQ)
class RegleProduitCPQAdmin(CompanyScopedAdmin):
    list_display = ('id', 'company', 'nom', 'actif', 'date_creation')
    list_filter = ('company', 'actif')


class LigneOffreGroupeeInline(admin.TabularInline):
    model = LigneOffreGroupee
    extra = 0


@admin.register(OffreGroupee)
class OffreGroupeeAdmin(CompanyScopedAdmin):
    list_display = ('id', 'company', 'nom', 'prix_total', 'actif')
    list_filter = ('company', 'actif')
    inlines = [LigneOffreGroupeeInline]


@admin.register(PrixContractuel)
class PrixContractuelAdmin(CompanyScopedAdmin):
    list_display = ('id', 'company', 'client', 'produit', 'prix_ht',
                    'date_debut', 'date_fin')
    list_filter = ('company',)


@admin.register(SeuilMargeFamille)
class SeuilMargeFamilleAdmin(CompanyScopedAdmin):
    list_display = ('id', 'company', 'categorie', 'marge_min_pct')
    list_filter = ('company',)


@admin.register(RegleApprobationRemise)
class RegleApprobationRemiseAdmin(CompanyScopedAdmin):
    list_display = ('id', 'company', 'libelle', 'remise_min_pct',
                    'remise_max_pct', 'nombre_approbateurs', 'actif')
    list_filter = ('company', 'actif')


@admin.register(EtapeApprobationDevis)
class EtapeApprobationDevisAdmin(CompanyScopedAdmin):
    list_display = ('id', 'company', 'devis', 'niveau', 'statut',
                    'approbateur')
    list_filter = ('company', 'statut')


@admin.register(QuestionConfigurateur)
class QuestionConfigurateurAdmin(CompanyScopedAdmin):
    list_display = ('id', 'company', 'ordre', 'texte', 'type', 'actif')
    list_filter = ('company', 'actif', 'type')


@admin.register(SessionConfigurateur)
class SessionConfigurateurAdmin(CompanyScopedAdmin):
    list_display = ('id', 'company', 'token', 'devis', 'created_at')
    list_filter = ('company',)


@admin.register(ReponseConfigurateur)
class ReponseConfigurateurAdmin(CompanyScopedAdmin):
    list_display = ('id', 'session', 'question', 'valeur')
