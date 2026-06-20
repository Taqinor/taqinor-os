"""N75 — Moteur de notifications unifié : in-app + (là où c'est configuré)
WhatsApp / email / SMS pour les événements clés du métier.

Principes (règles fondatrices) :
  - ADDITIF UNIQUEMENT : nouvelle app, nouveaux modèles, colonnes nullables.
  - MULTI-TENANT : chaque modèle porte `company` (FK authentication.Company) ET
    un destinataire `recipient` (utilisateur). Une notification appartient à UN
    utilisateur d'UNE société ; jamais lue/écrite depuis le corps de requête.
  - In-app TOUJOURS disponible ; les canaux WhatsApp/email/SMS RÉUTILISENT les
    intégrations existantes et sont des NO-OP sûrs quand rien n'est configuré.
  - Texte destiné à l'utilisateur en FRANÇAIS ; identifiants/code en anglais.

Les types d'événement sont une énumération fermée (clés stables en anglais,
libellés FR pour l'UI). On n'invente jamais d'événement à la volée : ajouter un
événement = ajouter une valeur ici.
"""
from django.conf import settings
from django.db import models


class EventType(models.TextChoices):
    """Événements métier déclencheurs de notification (clé EN, libellé FR)."""
    LEAD_ASSIGNED = 'lead_assigned', 'Nouveau lead assigné'
    DEVIS_ACCEPTED = 'devis_accepted', 'Devis accepté'
    CHANTIER_DUE = 'chantier_due', 'Chantier à installer'
    FACTURE_OVERDUE = 'facture_overdue', 'Facture en retard'
    WARRANTY_EXPIRING = 'warranty_expiring', 'Garantie bientôt expirée'
    MAINTENANCE_DUE = 'maintenance_due', 'Visite de maintenance due'
    STOCK_LOW = 'stock_low', 'Stock bas'
    SAV_TICKET_OPENED = 'sav_ticket_opened', 'Ticket SAV ouvert'
    SAV_TICKET_BREACHING = 'sav_ticket_breaching', 'Ticket SAV proche de son délai'
    DIGEST = 'digest', 'Récapitulatif'


class Channel(models.TextChoices):
    """Canaux de diffusion. `IN_APP` est toujours disponible ; les autres
    réutilisent les intégrations existantes et no-op si non configurés."""
    IN_APP = 'in_app', 'In-app'
    WHATSAPP = 'whatsapp', 'WhatsApp'
    EMAIL = 'email', 'Email'
    SMS = 'sms', 'SMS'


class Notification(models.Model):
    """Une notification in-app pour UN utilisateur d'UNE société.

    Toujours créée quand le canal in-app est activé pour l'événement. Les
    diffusions hors-app (WhatsApp/email/SMS) sont best-effort et n'ont pas de
    table dédiée : elles réutilisent les journaux des intégrations existantes."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='notifications')
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='notifications')
    event_type = models.CharField(
        max_length=40, choices=EventType.choices)
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True, default='')
    # Lien interne (route front) vers l'enregistrement lié — ex. /crm/leads?lead=4.
    link = models.CharField(max_length=512, blank=True, default='')
    read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['company', 'recipient', 'read']),
            models.Index(fields=['recipient', 'created_at']),
        ]

    def __str__(self):
        return f'{self.get_event_type_display()} → {self.recipient_id}'


class NotificationPreference(models.Model):
    """Préférence de canaux par utilisateur ET par type d'événement.

    Absence de ligne = défauts sensibles (voir `default_prefs`) : in-app activé,
    canaux hors-app désactivés (rien de spammeur). On ne crée une ligne que
    lorsque l'utilisateur modifie ses préférences."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='notification_preferences')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='notification_preferences')
    event_type = models.CharField(
        max_length=40, choices=EventType.choices)
    in_app = models.BooleanField(default=True)
    whatsapp = models.BooleanField(default=False)
    email = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Préférence de notification'
        verbose_name_plural = 'Préférences de notification'
        ordering = ['event_type']
        unique_together = [('user', 'event_type')]
        indexes = [
            models.Index(fields=['company', 'user']),
        ]

    def __str__(self):
        return f'{self.user_id} / {self.event_type}'


class PushSubscription(models.Model):
    """N92 — Abonnement Web Push d'un APPAREIL pour un utilisateur d'une société.

    Opt-in par appareil : le navigateur fournit un `endpoint` unique + les clés
    de chiffrement (`p256dh`, `auth`). MULTI-TENANT : `company` et `user` sont
    posés CÔTÉ SERVEUR (jamais lus du corps de requête). Un même utilisateur peut
    avoir plusieurs abonnements (un par appareil/navigateur). ADDITIF : aucun
    abonnement = comportement actuel (aucun push). Quand les clés VAPID sont
    absentes, ces lignes restent inertes (le moteur ne les utilise pas)."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='push_subscriptions')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='push_subscriptions')
    # Endpoint unique fourni par le PushManager du navigateur (identifie l'appareil).
    endpoint = models.URLField(max_length=1000, unique=True)
    # Clés de chiffrement de l'abonnement (base64url) — requises par Web Push.
    p256dh = models.CharField(max_length=255)
    auth = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Abonnement push'
        verbose_name_plural = 'Abonnements push'
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['company', 'user']),
        ]

    def __str__(self):
        return f'{self.user_id} @ {self.endpoint[:40]}'

    def as_subscription_info(self):
        """Format `subscription_info` attendu par pywebpush."""
        return {
            'endpoint': self.endpoint,
            'keys': {'p256dh': self.p256dh, 'auth': self.auth},
        }
