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
import logging

from django.conf import settings
from django.db import models, transaction

logger = logging.getLogger(__name__)


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
    # Group S — messagerie interne (« Discuss »).
    CHAT_MESSAGE = 'chat_message', 'Nouveau message'
    CHAT_MENTION = 'chat_mention', 'Vous avez été mentionné'
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


class NotificationRoutingRule(models.Model):
    """FG4 — Règle de routage des notifications configurable par l'admin.

    Détermine QUELS utilisateurs reçoivent les notifications d'un type
    d'événement donné. Deux modes :
      - `target_role` (ex. 'admin', 'responsable') : tous les utilisateurs
        actifs de la société ayant ce rôle legacy reçoivent la notification.
      - `target_user` : un utilisateur précis de la société.

    Absence de règle = comportement actuel préservé (la fonction `notify()`
    utilise `_is_manager` comme avant). ADDITIF : sans règle configurée, rien
    ne change. Multi-tenant : chaque règle appartient à UNE société.
    """

    ROLE_CHOICES = [
        ('admin', 'Administrateur'),
        ('responsable', 'Responsable'),
        ('normal', 'Utilisateur normal'),
    ]

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='notification_routing_rules')
    event_type = models.CharField(
        max_length=40, choices=EventType.choices,
        verbose_name='Type d\'événement')
    # Ciblage par rôle OU par utilisateur (au moins l'un des deux doit être renseigné).
    target_role = models.CharField(
        max_length=20, choices=ROLE_CHOICES,
        null=True, blank=True, verbose_name='Rôle cible')
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        null=True, blank=True, related_name='notification_routing_rules',
        verbose_name='Utilisateur cible')
    enabled = models.BooleanField(default=True, verbose_name='Actif')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Règle de routage des notifications'
        verbose_name_plural = 'Règles de routage des notifications'
        ordering = ['event_type', 'id']
        indexes = [
            models.Index(fields=['company', 'event_type', 'enabled']),
        ]

    def __str__(self):
        if self.target_user_id:
            return f'{self.get_event_type_display()} → user:{self.target_user_id}'
        return f'{self.get_event_type_display()} → role:{self.target_role}'

    def clean(self):
        from django.core.exceptions import ValidationError
        if not self.target_role and not self.target_user_id:
            raise ValidationError(
                'Une règle de routage doit cibler soit un rôle, soit un utilisateur.')


class VapidKeyPair(models.Model):
    """N109 — Paire de clés VAPID auto-générée, persistée en singleton global.

    INFRA APPLICATIVE, PAS une donnée métier : c'est une exception EXPLICITEMENT
    autorisée à la règle multi-tenant — aucune `company` FK. Une seule ligne
    existe pour toute l'instance ; toutes les sociétés partagent la même paire
    VAPID (la clé identifie le SERVEUR auprès des services push, pas un tenant).

    Renseignée à la volée par `ensure()` quand aucune clé n'est fournie par
    l'environnement, pour que le web push fonctionne sans configuration manuelle.
    `public_key` est au format base64url (point EC brut non compressé, la forme
    attendue par `applicationServerKey` du navigateur) ; `private_key` est un PEM
    accepté tel quel par `pywebpush.webpush(vapid_private_key=...)`."""

    public_key = models.TextField(default='')
    private_key = models.TextField(default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Paire de clés VAPID'
        verbose_name_plural = 'Paires de clés VAPID'

    def __str__(self):
        return f'VapidKeyPair #{self.pk}'

    @classmethod
    def _generate(cls):
        """Génère (public_b64, private_pem) ou (None, None) en cas d'échec.

        Best-effort : toute erreur (lib absente, etc.) renvoie (None, None) ;
        jamais d'exception remontée."""
        try:
            import base64

            from cryptography.hazmat.primitives import serialization
            from py_vapid import Vapid01

            v = Vapid01()
            v.generate_keys()
            raw_pub = v.public_key.public_bytes(
                serialization.Encoding.X962,
                serialization.PublicFormat.UncompressedPoint)
            public_b64 = base64.urlsafe_b64encode(raw_pub).rstrip(b'=').decode()
            priv_pem = v.private_pem().decode()
            if not public_b64 or not priv_pem:
                return (None, None)
            return (public_b64, priv_pem)
        except Exception as exc:  # pragma: no cover - lib absente / défensif
            logger.warning('Génération de la paire VAPID échouée : %s', exc)
            return (None, None)

    @classmethod
    def ensure(cls):
        """Renvoie le singleton existant, sinon le génère et le persiste.

        Sémantique singleton : une seule ligne pour toute l'instance. Génération
        gardée par une transaction + `select_for_update` pour éviter qu'une course
        crée deux lignes. Renvoie l'instance, ou None si la génération échoue
        (lib absente, etc.) — jamais d'exception remontée."""
        try:
            existing = cls.objects.first()
            if existing is not None:
                return existing
            with transaction.atomic():
                existing = cls.objects.select_for_update().first()
                if existing is not None:
                    return existing
                public_b64, priv_pem = cls._generate()
                if not public_b64 or not priv_pem:
                    return None
                return cls.objects.create(
                    public_key=public_b64, private_key=priv_pem)
        except Exception as exc:  # pragma: no cover - défensif
            logger.warning('Initialisation de la paire VAPID échouée : %s', exc)
            return None


# =============================================================================
# QJ23 — WhatsApp BSP scaffold (flag-gated, défaut manuel wa.me)
# =============================================================================

class WhatsAppTemplate(models.Model):
    """Registre des gabarits BSP WhatsApp approuvés par Meta, par entreprise.

    ADDITIF : sans aucune ligne, le comportement actuel (wa.me manuel) est
    préservé à 100 %. Ce modèle ne remplace PAS `parametres.MessageTemplate`
    (messages éditables manuels) — il ajoute le registre BSP (gabarits approuvés
    côté Meta, avec leur nom et leur langue).

    MULTI-TENANT : `company` est forcé côté serveur, jamais accepté du corps.
    Ne jamais exposer prix_achat / marge dans un message.
    """

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='whatsapp_bsp_templates')
    # Nom du gabarit tel qu'approuvé par Meta (ex. 'devis_envoye_v1').
    name = models.CharField(max_length=100, verbose_name='Nom du gabarit Meta')
    # Corps du message en français (texte de référence interne — le texte réel
    # est côté Meta ; ici c'est un aide-mémoire éditable).
    body_fr = models.TextField(blank=True, default='', verbose_name='Corps FR (aide-mémoire)')
    # Code langue IETF (ex. 'fr', 'ar', 'fr_MA') — défaut FR.
    language = models.CharField(max_length=10, default='fr', verbose_name='Langue')
    active = models.BooleanField(default=True, verbose_name='Actif')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Gabarit WhatsApp BSP'
        verbose_name_plural = 'Gabarits WhatsApp BSP'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'name', 'language'],
                name='notif_wa_tpl_company_name_lang_uniq',
            ),
        ]
        indexes = [
            models.Index(fields=['company', 'active'], name='notif_wa_tpl_company_active_idx'),
        ]

    def __str__(self):
        return f'{self.company_id}:{self.name}:{self.language}'


class WhatsAppMessageLog(models.Model):
    """Journal des messages WhatsApp (envois BSP + liens manuels wa.me).

    Chaque tentative d'envoi ou de construction de lien wa.me peut laisser
    une trace ici. Les mises à jour de statut (livré/lu) arrivent via le
    webhook BSP et mettent à jour la ligne correspondante via `external_id`.

    MULTI-TENANT : `company` forcé côté serveur.
    Ne jamais stocker prix_achat / marge dans `body`.
    """

    class Status(models.TextChoices):
        QUEUED = 'queued', 'En attente'
        SENT = 'sent', 'Envoyé'
        DELIVERED = 'delivered', 'Distribué'
        READ = 'read', 'Lu'
        FAILED = 'failed', 'Échec'
        MANUAL = 'manual', 'Manuel (wa.me)'

    class Provider(models.TextChoices):
        MANUAL = 'manual', 'Manuel (wa.me)'
        BSP = 'bsp', 'BSP (API WhatsApp Business)'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='whatsapp_message_logs')
    # Destinataire (numéro normalisé, ex. 2126xxxxxxxx).
    recipient = models.CharField(max_length=30, verbose_name='Destinataire')
    # Corps du message (ou référence au gabarit). NE PAS y mettre prix_achat.
    body = models.TextField(blank=True, default='', verbose_name='Corps')
    # Gabarit BSP utilisé (nullable — None pour les messages libres / manuels).
    template = models.ForeignKey(
        WhatsAppTemplate, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='message_logs',
        verbose_name='Gabarit BSP')
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.MANUAL,
        verbose_name='Statut')
    provider = models.CharField(
        max_length=20, choices=Provider.choices, default=Provider.MANUAL,
        verbose_name='Fournisseur')
    # ID externe renvoyé par l'API Meta (permet de relier les webhooks).
    external_id = models.CharField(
        max_length=255, blank=True, default='', db_index=True,
        verbose_name='ID externe Meta')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Journal WhatsApp'
        verbose_name_plural = 'Journal WhatsApp'
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(
                fields=['company', 'recipient', 'status'],
                name='notif_wa_log_company_recip_st_idx',
            ),
            models.Index(
                fields=['company', 'created_at'],
                name='notif_wa_log_company_created_idx',
            ),
        ]

    def __str__(self):
        return f'WA:{self.provider}:{self.status} → {self.recipient}'
