from django.contrib import admin

from .models import KbArticle


@admin.register(KbArticle)
class KbArticleAdmin(admin.ModelAdmin):
    list_display = ('id', 'titre', 'categorie', 'statut', 'auteur', 'company',
                    'date_modification')
    list_filter = ('statut', 'categorie')
    search_fields = ('titre', 'corps', 'categorie', 'tags')
