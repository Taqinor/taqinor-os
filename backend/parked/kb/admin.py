from django.contrib import admin

from core.admin_scoping import CompanyScopedAdminMixin

from .models import (
    BlocReutilisable,
    KbArticle,
    KbArticleAcl,
    KbArticleLien,
    KbArticleVersion,
    KbFavori,
    KbLecture,
    KbLectureObligatoire,
    KbParcours,
    KbParcoursArticle,
    KbParcoursAssignation,
    KbRechercheVide,
    PartageArticleKb,
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


@admin.register(KbArticle)
class KbArticleAdmin(CompanyScopedAdmin):
    list_display = ('id', 'titre', 'categorie', 'statut', 'visibilite',
                    'parent', 'auteur', 'company', 'date_modification')
    list_filter = ('statut', 'categorie', 'visibilite')
    search_fields = ('titre', 'corps', 'categorie', 'tags')


@admin.register(KbArticleVersion)
class KbArticleVersionAdmin(CompanyScopedAdmin):
    list_display = ('id', 'article', 'version', 'titre', 'auteur', 'company',
                    'date_creation')
    list_filter = ('company',)
    search_fields = ('titre', 'contenu')


@admin.register(KbArticleLien)
class KbArticleLienAdmin(CompanyScopedAdmin):
    list_display = ('id', 'article', 'type_cible', 'cible_id', 'libelle',
                    'company', 'date_creation')
    list_filter = ('type_cible', 'company')
    search_fields = ('libelle',)


@admin.register(KbArticleAcl)
class KbArticleAclAdmin(CompanyScopedAdmin):
    list_display = ('id', 'article', 'role', 'utilisateur', 'niveau',
                    'company', 'date_creation')
    list_filter = ('role', 'niveau', 'company')


@admin.register(KbLecture)
class KbLectureAdmin(CompanyScopedAdmin):
    list_display = ('id', 'article', 'utilisateur', 'company', 'lu_le')
    list_filter = ('company',)


@admin.register(KbLectureObligatoire)
class KbLectureObligatoireAdmin(CompanyScopedAdmin):
    list_display = ('id', 'article', 'utilisateur', 'role_cible', 'echeance',
                    'company', 'date_creation')
    list_filter = ('role_cible', 'company')


@admin.register(KbFavori)
class KbFavoriAdmin(CompanyScopedAdmin):
    list_display = ('id', 'article', 'utilisateur', 'company', 'date_creation')
    list_filter = ('company',)


@admin.register(KbRechercheVide)
class KbRechercheVideAdmin(CompanyScopedAdmin):
    list_display = ('id', 'terme', 'utilisateur', 'company', 'date_creation')
    list_filter = ('company',)
    search_fields = ('terme',)


@admin.register(PartageArticleKb)
class PartageArticleKbAdmin(CompanyScopedAdmin):
    list_display = ('id', 'article', 'actif', 'expires_at', 'consultations',
                    'company', 'date_creation')
    list_filter = ('actif', 'company')


@admin.register(KbParcours)
class KbParcoursAdmin(CompanyScopedAdmin):
    list_display = ('id', 'nom', 'role_cible', 'metier', 'actif', 'company',
                    'date_creation')
    list_filter = ('actif', 'role_cible', 'company')
    search_fields = ('nom', 'metier')


@admin.register(KbParcoursArticle)
class KbParcoursArticleAdmin(CompanyScopedAdmin):
    list_display = ('id', 'parcours', 'article', 'ordre', 'company')
    list_filter = ('company',)


@admin.register(KbParcoursAssignation)
class KbParcoursAssignationAdmin(CompanyScopedAdmin):
    list_display = ('id', 'parcours', 'utilisateur', 'company', 'date_creation')
    list_filter = ('company',)


@admin.register(BlocReutilisable)
class BlocReutilisableAdmin(CompanyScopedAdmin):
    list_display = ('id', 'nom', 'portee', 'created_by', 'company',
                    'date_creation')
    list_filter = ('portee', 'company')
    search_fields = ('nom', 'corps')
