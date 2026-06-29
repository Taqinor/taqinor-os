from django.contrib import admin

from .models import (
    KbArticle,
    KbArticleAcl,
    KbArticleLien,
    KbArticleVersion,
    KbLecture,
)


@admin.register(KbArticle)
class KbArticleAdmin(admin.ModelAdmin):
    list_display = ('id', 'titre', 'categorie', 'statut', 'auteur', 'company',
                    'date_modification')
    list_filter = ('statut', 'categorie')
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
    list_display = ('id', 'article', 'role', 'niveau', 'company',
                    'date_creation')
    list_filter = ('role', 'niveau', 'company')


@admin.register(KbLecture)
class KbLectureAdmin(admin.ModelAdmin):
    list_display = ('id', 'article', 'utilisateur', 'company', 'lu_le')
    list_filter = ('company',)
