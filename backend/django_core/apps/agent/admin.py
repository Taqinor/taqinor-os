"""AIC6 — admin Django en LECTURE SEULE du journal de l'assistant."""
from django.contrib import admin

from .models import AssistantEvent


@admin.register(AssistantEvent)
class AssistantEventAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'company', 'user', 'intention', 'modele',
                    'repli', 'note')
    list_filter = ('intention', 'repli', 'note', 'company')
    search_fields = ('question', 'resume_reponse')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
