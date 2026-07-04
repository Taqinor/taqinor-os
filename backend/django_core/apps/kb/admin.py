from django.contrib import admin

from .models import (
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


@admin.register(KbArticle)
class KbArticleAdmin(admin.ModelAdmin):
    list_display = ('id', 'titre', 'categorie', 'statut', 'visibilite',
                    'parent', 'auteur', 'company', 'date_modification')
    list_filter = ('statut', 'categorie', 'visibilite')
    search_fields = ('titre', 'corps', 'categorie', 'tags')


@admin.register(KbArticleVersion)
class KbArticleVersionAdmin(admin.ModelAdmin):
    list_display = ('id', 'article', 'version', 'titre', 'auteur', 'company',
                    'date_creation')
    list_filter = ('company',)
    search_fields = ('titre', 'contenu')


@admin.register(KbArticleLien)
class KbArticleLienAdmin(admin.ModelAdmin):
    list_display = ('id', 'article', 'type_cible', 'cible_id', 'libelle',
                    'company', 'date_creation')
    list_filter = ('type_cible', 'company')
    search_fields = ('libelle',)


@admin.register(KbArticleAcl)
class KbArticleAclAdmin(admin.ModelAdmin):
    list_display = ('id', 'article', 'role', 'utilisateur', 'niveau',
                    'company', 'date_creation')
    list_filter = ('role', 'niveau', 'company')


@admin.register(KbLecture)
class KbLectureAdmin(admin.ModelAdmin):
    list_display = ('id', 'article', 'utilisateur', 'company', 'lu_le')
    list_filter = ('company',)


@admin.register(KbLectureObligatoire)
class KbLectureObligatoireAdmin(admin.ModelAdmin):
    list_display = ('id', 'article', 'utilisateur', 'role_cible', 'echeance',
                    'company', 'date_creation')
    list_filter = ('role_cible', 'company')


@admin.register(KbFavori)
class KbFavoriAdmin(admin.ModelAdmin):
    list_display = ('id', 'article', 'utilisateur', 'company', 'date_creation')
    list_filter = ('company',)


@admin.register(KbRechercheVide)
class KbRechercheVideAdmin(admin.ModelAdmin):
    list_display = ('id', 'terme', 'utilisateur', 'company', 'date_creation')
    list_filter = ('company',)
    search_fields = ('terme',)


@admin.register(PartageArticleKb)
class PartageArticleKbAdmin(admin.ModelAdmin):
    list_display = ('id', 'article', 'actif', 'expires_at', 'consultations',
                    'company', 'date_creation')
    list_filter = ('actif', 'company')


@admin.register(KbParcours)
class KbParcoursAdmin(admin.ModelAdmin):
    list_display = ('id', 'nom', 'role_cible', 'metier', 'actif', 'company',
                    'date_creation')
    list_filter = ('actif', 'role_cible', 'company')
    search_fields = ('nom', 'metier')


@admin.register(KbParcoursArticle)
class KbParcoursArticleAdmin(admin.ModelAdmin):
    list_display = ('id', 'parcours', 'article', 'ordre', 'company')
    list_filter = ('company',)


@admin.register(KbParcoursAssignation)
class KbParcoursAssignationAdmin(admin.ModelAdmin):
    list_display = ('id', 'parcours', 'utilisateur', 'company', 'date_creation')
    list_filter = ('company',)
