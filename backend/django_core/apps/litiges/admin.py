from django.contrib import admin

from core.admin_scoping import CompanyScopedAdminMixin

from .models import Reclamation, ReclamationActivity


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


@admin.register(Reclamation)
class ReclamationAdmin(CompanyScopedAdmin):
    list_display = ('id', 'objet', 'type_reclamation', 'gravite', 'statut',
                    'montant_conteste', 'concurrent_nom', 'company',
                    'date_creation')
    list_filter = ('type_reclamation', 'gravite', 'statut')
    search_fields = ('reference', 'objet', 'description', 'concurrent_nom',
                     'motif_perte')


@admin.register(ReclamationActivity)
class ReclamationActivityAdmin(CompanyScopedAdmin):
    list_display = ('id', 'reclamation', 'type', 'old_value', 'new_value',
                    'auteur', 'company', 'date_creation')
    list_filter = ('type',)
    search_fields = ('message',)
