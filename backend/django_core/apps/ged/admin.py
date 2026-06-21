from django.contrib import admin

from .models import Document, DocumentVersion, Dossier


@admin.register(Dossier)
class DossierAdmin(admin.ModelAdmin):
    list_display = ('id', 'nom', 'parent', 'chemin', 'company')
    list_filter = ('company',)
    search_fields = ('nom', 'chemin')


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('id', 'titre', 'dossier', 'statut', 'created_by', 'company')
    list_filter = ('company', 'statut')
    search_fields = ('titre', 'description')


@admin.register(DocumentVersion)
class DocumentVersionAdmin(admin.ModelAdmin):
    list_display = ('id', 'document', 'numero_version', 'filename', 'taille',
                    'company')
    list_filter = ('company',)
    search_fields = ('filename', 'file_key', 'checksum')
