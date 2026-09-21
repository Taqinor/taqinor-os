"""WIR49 — Filet de sécurité Django admin pour les modèles Flotte critiques.

``apps/flotte`` n'avait AUCUN ``admin.py`` (contrairement à ``paie``) : aucun
des gaps d'écriture flotte n'avait de filet en attendant les écrans dédiés.
Enregistre au minimum les modèles sans chemin de création UI au moment de
l'audit (``Conducteur``, ``GarantieFlotte``, ``BudgetFlotte``,
``RemiseAccessoire``, ``DemandeVehicule``). ``company`` reste un champ
ÉDITABLE normal (comme dans ``apps/paie/admin.py``) — elle est requise sans
défaut au niveau modèle, la rendre lecture seule empêcherait toute création.
"""
from django.contrib import admin

from core.admin_scoping import CompanyScopedAdminMixin

from .models import (
    BudgetFlotte,
    Conducteur,
    DemandeVehicule,
    GarantieFlotte,
    RemiseAccessoire,
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


@admin.register(Conducteur)
class ConducteurAdmin(CompanyScopedAdmin):
    list_display = (
        'id', 'nom', 'telephone', 'numero_permis', 'categorie_permis',
        'date_expiration', 'actif', 'company',
    )
    list_filter = ('actif', 'company')
    search_fields = ('nom', 'numero_permis', 'telephone')
    readonly_fields = ('date_creation',)


@admin.register(GarantieFlotte)
class GarantieFlotteAdmin(CompanyScopedAdmin):
    list_display = (
        'id', 'actif_flotte', 'composant', 'duree_mois', 'duree_km',
        'date_debut', 'fournisseur', 'company',
    )
    list_filter = ('company',)
    search_fields = ('composant', 'fournisseur')


@admin.register(BudgetFlotte)
class BudgetFlotteAdmin(CompanyScopedAdmin):
    list_display = (
        'id', 'annee', 'categorie', 'montant_budgete',
        'notifie_depassement', 'company',
    )
    list_filter = ('annee', 'categorie', 'company')
    # `notifie_depassement` est géré côté serveur (services.py) — jamais saisi.
    readonly_fields = ('notifie_depassement', 'date_creation')


@admin.register(RemiseAccessoire)
class RemiseAccessoireAdmin(CompanyScopedAdmin):
    list_display = (
        'id', 'actif_flotte', 'type_accessoire', 'conducteur',
        'date_remise', 'date_retour', 'company',
    )
    list_filter = ('type_accessoire', 'company')
    # NB : `ActifFlotte.label` est une propriété Python calculée (pas une
    # colonne DB, voir models.py) — non utilisable en `search_fields`.
    search_fields = ('conducteur__nom',)
    readonly_fields = ('date_creation',)


@admin.register(DemandeVehicule)
class DemandeVehiculeAdmin(CompanyScopedAdmin):
    list_display = (
        'id', 'demandeur', 'besoin', 'date_debut_souhaitee',
        'date_fin_souhaitee', 'statut', 'vehicule_attribue', 'company',
    )
    list_filter = ('statut', 'company')
    search_fields = ('besoin', 'demandeur__username')
    # La décision (approuver/refuser) passe par les actions dédiées de l'API —
    # jamais un PATCH admin direct.
    readonly_fields = ('decide_par', 'date_decision', 'date_creation')
