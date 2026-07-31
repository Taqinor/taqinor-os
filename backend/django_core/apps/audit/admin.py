from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Journal d'activité — surface LECTURE SEULE dans l'administration Django.

    Ajouté avec les gardes de champ de `ProduitAdmin` (voir
    apps/stock/admin.py, `CHAMP_CATALOGUE_VIDE_INTERDIT`) : `stock.Produit` et
    `crm.Client` figurent déjà dans `apps.audit.signals.TRACKED_MODELS`, donc
    TOUTE sauvegarde faite depuis /admin/ — y compris un `prix_achat`/
    `courbe_pompe` modifié — pose déjà, automatiquement, une ligne `AuditLog`
    avec un diff structuré (`changes`, ancien → nouveau). Ce modèle n'avait
    simplement aucun `admin.py` : la trace existait mais restait invisible
    depuis l'admin lui-même (il fallait connaître l'écran Journal du frontend
    ERP, ou interroger la base). Cet enregistrement la rend VISIBLE au même
    endroit que l'édition qui l'a produite.

    Lecture seule de bout en bout : l'admin Django ne doit JAMAIS devenir un
    second point d'écriture pour un journal d'inviolabilité (chaînage de hash
    NTSEC17) — la purge légitime reste `manage.py purge_audit_log`.
    """
    list_display = (
        'timestamp', 'action', 'company', 'actor_username', 'content_type',
        'object_repr', 'detail',
    )
    list_filter = ('action', 'company', 'content_type')
    search_fields = ('actor_username', 'object_repr', 'detail', 'object_id')
    date_hierarchy = 'timestamp'
    readonly_fields = (
        'company', 'user', 'actor_username', 'action', 'content_type',
        'object_id', 'object_repr', 'detail', 'changes', 'prev_hash',
        'entry_hash', 'timestamp',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
