from django.contrib import admin

from .models import ApiKey, Webhook, WebhookDelivery


@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    list_display = ('label', 'prefix', 'company', 'enabled', 'created_at',
                    'last_used_at')
    list_filter = ('enabled', 'company')
    readonly_fields = ('key_hash', 'prefix', 'created_at', 'last_used_at')


@admin.register(Webhook)
class WebhookAdmin(admin.ModelAdmin):
    """AUD405 — le secret HMAC ne quitte JAMAIS le serveur par l'admin.

    Défaut corrigé : ``secret`` figurait dans ``readonly_fields`` — or un champ
    en lecture seule reste RENDU, pas caché. Comme ``Webhook.secret`` est un
    ``EncryptedCharField`` déchiffré à chaque chargement ORM, ouvrir
    ``/admin/publicapi/webhook/<id>/change/`` affichait en clair le secret qui
    signe TOUS les webhooks sortants de la société (``X-Taqinor-Signature``) —
    de quoi forger de faux évènements ``facture.paid``/``devis.accepted`` vers
    l'intégration du client, qui se fie à cette signature comme preuve
    d'authenticité. Contraste : ``ApiKeyAdmin`` n'expose que ``key_hash``, un
    HMAC irréversible.

    Le secret est donc EXCLU du formulaire (jamais rendu), remplacé par un
    témoin masqué, et seulement re-générable via une action dédiée qui affiche
    la nouvelle valeur UNE SEULE FOIS (patron ``ApiKey.rotate()``).
    """

    list_display = ('label', 'target_url', 'company', 'enabled', 'created_at')
    list_filter = ('enabled', 'company')
    exclude = ('secret',)
    readonly_fields = ('secret_masque', 'created_at')
    actions = ['regenerer_secret']

    @admin.display(description='Secret de signature')
    def secret_masque(self, obj=None):
        """Témoin : le secret existe, mais sa valeur ne s'affiche jamais."""
        if obj is None or not obj.pk:
            return 'Généré automatiquement à la création.'
        return ('•••••••••••••••• (masqué — utilisez l’action « Régénérer le '
                'secret » pour en obtenir un nouveau)')

    def get_queryset(self, request):
        """Scoping société (défense en profondeur).

        Un compte rattaché à une société ne voit que SES webhooks ; un opérateur
        de plateforme sans société d'attache garde la vue complète (sans quoi la
        console d'administration deviendrait inutilisable pour lui). Le secret
        n'est de toute façon plus rendu, quel que soit le lecteur.
        """
        qs = super().get_queryset(request)
        company = getattr(getattr(request, 'user', None), 'company', None)
        if company is not None:
            return qs.filter(company=company)
        return qs

    def save_model(self, request, obj, form, change):
        """Le secret est posé côté SERVEUR (le formulaire ne le porte plus)."""
        if not obj.secret:
            obj.secret = Webhook.generate_secret()
        super().save_model(request, obj, form, change)

    @admin.action(description='Régénérer le secret de signature')
    def regenerer_secret(self, request, queryset):
        """Rotation explicite : la nouvelle valeur est montrée UNE fois.

        Rappel affiché à l'opérateur : l'ancien secret cesse immédiatement de
        signer, l'intégration du client doit être mise à jour.
        """
        for webhook in queryset:
            nouveau = Webhook.generate_secret()
            webhook.secret = nouveau
            webhook.save(update_fields=['secret'])
            self.message_user(
                request,
                f'{webhook} — nouveau secret (affiché une seule fois) : '
                f'{nouveau}',
            )


@admin.register(WebhookDelivery)
class WebhookDeliveryAdmin(admin.ModelAdmin):
    list_display = ('event', 'webhook', 'status', 'response_status',
                    'created_at')
    list_filter = ('status', 'event', 'company')
    readonly_fields = ('created_at',)
