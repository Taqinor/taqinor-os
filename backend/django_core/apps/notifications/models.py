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
événement = ajouter une valeur dans ``types_evenements.py`` (SPL303).
"""
import logging

from django.conf import settings
from django.db import models, transaction

from core.crypto_fields import EncryptedTextField
from core.models import TenantModel

logger = logging.getLogger(__name__)


# Lu par les 3 champs ``event_type`` ci-dessous ET importé d'ici par les
# migrations 0039-0064 (append-only) : ne pas retirer (SPL303).
from .types_evenements import EventType  # noqa: E402


class Channel(models.TextChoices):
    """Canaux de diffusion. `IN_APP` est toujours disponible ; les autres
    réutilisent les intégrations existantes et no-op si non configurés."""
    IN_APP = 'in_app', 'In-app'
    WHATSAPP = 'whatsapp', 'WhatsApp'
    EMAIL = 'email', 'Email'
    SMS = 'sms', 'SMS'


class NotificationReason(models.TextChoices):
    """VX212(a) — raison COURTE, fermée, de « pourquoi je reçois ça ».

    `resolve_recipients` (services.py) applique des règles invisibles — des
    notifs « pourquoi moi ? » qu'on ne pouvait couper qu'en fouillant la
    grille des 42 événements. Un sous-ensemble REPRÉSENTATIF des sites
    d'émission pose désormais cette raison (jamais une exception si non
    posée — vide = comportement historique, raison inconnue/non classée)."""
    ASSIGNE = 'assigne_a_vous', 'Assigné à vous'
    MANAGER = 'manager', 'Vous êtes manager/responsable'
    ROUTING_RULE = 'regle_de_routage', 'Règle de routage configurée'
    FOLLOWING = 'vous_suivez', 'Vous suivez cet enregistrement'


class Notification(models.Model):
    """Une notification in-app pour UN utilisateur d'UNE société.

    Toujours créée quand le canal in-app est activé pour l'événement. Les
    diffusions hors-app (WhatsApp/email/SMS) sont best-effort et n'ont pas de
    table dédiée : elles réutilisent les journaux des intégrations existantes."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: tenant (societe)
        null=True, blank=True, related_name='notifications')
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,  # on_delete: composition (utilisateur)
        related_name='notifications')
    event_type = models.CharField(
        max_length=40, choices=EventType.choices)
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True, default='')
    # Lien interne (route front) vers l'enregistrement lié — ex. /crm/leads?lead=4.
    link = models.CharField(max_length=512, blank=True, default='')
    # VX212(a) — « pourquoi je reçois ça » : posé au site d'émission (best-
    # effort, optionnel). Vide = raison non classée (comportement historique).
    reason = models.CharField(
        max_length=20, choices=NotificationReason.choices, blank=True, default='')
    read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # VX209(c) — une notification NON LUE de plus de 60 j est archivée (jamais
    # supprimée — l'historique reste consultable) par la purge périodique
    # `purge_notifications_anciennes` ; les LUES de plus de 60 j sont
    # supprimées. Exclue par défaut de `list()` (borné 90 j) — comportement
    # historique inchangé pour tout le monde tant que rien n'a 60 j.
    archived = models.BooleanField(default=False)
    # N1 (décision fondateur du 25/09/2026) — « aucune notification à minuit
    # ni à 23 h ; garde-les toutes, mais aux heures de travail ». Une
    # notification émise HORS de la fenêtre de messages de sa société
    # (`selectors.fenetre_notifications`) est CRÉÉE tout de suite mais porte
    # ici l'instant où elle sera livrée ; tant que ce champ est posé elle
    # n'apparaît nulle part (ni cloche, ni compteur, ni push/e-mail). Le
    # balayage `notifications.livrer_differees` (toutes les 5 min) la livre à
    # échéance puis remet le champ à NULL. NULL = notification livrée
    # (comportement historique de toutes les lignes existantes).
    programmee_pour = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['company', 'recipient', 'read']),
            models.Index(fields=['recipient', 'created_at']),
            # N1 — index PARTIEL : seules les lignes en attente de livraison
            # y entrent (quelques dizaines par nuit), jamais l'historique.
            models.Index(
                fields=['programmee_pour'], name='notif_programmee_pour_idx',
                condition=models.Q(programmee_pour__isnull=False)),
        ]

    def __str__(self):
        return f'{self.get_event_type_display()} → {self.recipient_id}'


class NotificationPreference(models.Model):
    """Préférence de canaux par utilisateur ET par type d'événement.

    Absence de ligne = défauts sensibles (voir `default_prefs`) : in-app activé,
    canaux hors-app désactivés (rien de spammeur). On ne crée une ligne que
    lorsque l'utilisateur modifie ses préférences."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: tenant (societe)
        null=True, blank=True, related_name='notification_preferences')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,  # on_delete: composition (utilisateur)
        related_name='notification_preferences')
    event_type = models.CharField(
        max_length=40, choices=EventType.choices)
    in_app = models.BooleanField(default=True)
    whatsapp = models.BooleanField(default=False)
    email = models.BooleanField(default=False)
    # NTMOB8 — opt-in PUSH par catégorie d'événement, sur CET appareil (au-delà
    # de l'opt-in device global N92/PushSubscription qu'il ne duplique pas :
    # le push n'est envoyé que si l'appareil a un abonnement ET que cette
    # catégorie reste activée). Défaut True = comportement historique
    # inchangé (le push partait déjà pour tout événement dès qu'un abonnement
    # existait, sans distinction de catégorie).
    push = models.BooleanField(default=True)

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
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: tenant (societe)
        null=True, blank=True, related_name='push_subscriptions')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,  # on_delete: composition (utilisateur)
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
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: tenant (societe)
        related_name='notification_routing_rules')
    event_type = models.CharField(
        max_length=40, choices=EventType.choices,
        verbose_name='Type d\'événement')
    # Ciblage par rôle OU par utilisateur (au moins l'un des deux doit être renseigné).
    target_role = models.CharField(
        max_length=20, choices=ROLE_CHOICES,
        null=True, blank=True, verbose_name='Rôle cible')
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,  # on_delete: composition (utilisateur)
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
    private_key = EncryptedTextField(default='')
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
# FG5 — Calendrier ouvré par société : config horaires + jours fériés marocains
# =============================================================================

class WorkingHoursConfig(models.Model):
    """Configuration des jours ouvrés pour une société.

    `working_days` est un entier bitmask (bits 0=Lundi … 6=Dimanche, LSB=Lundi).
    La valeur par défaut 0b00011111 (= 31) représente Lundi–Vendredi.
    Les helpers de `calendar_utils` lisent ce masque pour décider si un jour
    est ouvré. ADDITIF : sans ligne, les helpers tombent sur les défauts (L–V).
    MULTI-TENANT : singleton par société, posé côté serveur.
    """

    # Bitmask : bit 0 = Lundi, bit 1 = Mardi, …, bit 6 = Dimanche.
    # L–V uniquement = 0b00011111 = 31.
    LUNDI = 0
    MARDI = 1
    MERCREDI = 2
    JEUDI = 3
    VENDREDI = 4
    SAMEDI = 5
    DIMANCHE = 6

    # Défaut Maroc : Lundi–Vendredi (bits 0–4).
    DEFAULT_WORKING_DAYS = 0b00011111  # 31

    company = models.OneToOneField(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: tenant (societe)
        related_name='notif_working_hours_config',
        verbose_name='Société')
    # Bitmask des jours ouvrés (Lundi=bit0 … Dimanche=bit6).
    working_days = models.PositiveSmallIntegerField(
        default=DEFAULT_WORKING_DAYS,
        verbose_name='Jours ouvrés (bitmask)')
    # Durée standard d'une journée de travail (information mémorisée, non
    # utilisée par les helpers de date — gardée pour usage futur).
    hours_per_day = models.DecimalField(
        max_digits=4, decimal_places=2, default='8.00',
        verbose_name='Heures / jour')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuration des heures ouvrées'
        verbose_name_plural = 'Configurations des heures ouvrées'

    def __str__(self):
        return f'WorkingHoursConfig [{self.company_id}]'

    def is_working_weekday(self, weekday: int) -> bool:
        """Renvoie True si `weekday` (0=Lun … 6=Dim) est coché comme ouvré."""
        return bool(self.working_days & (1 << weekday))


class Holiday(models.Model):
    """Jour férié par société.

    `date` = date exacte du jour férié pour cette année.
    `recurrent_annuel` = True → la date est annuelle (anniversaire ; seul le
    mois + le jour comptent, l'année de `date` sert de référence).
    Les fêtes islamiques (Id al-Fitr, Id al-Adha, etc.) varient d'année en
    année (calendrier lunaire) et DOIVENT être saisies manuellement.
    Le seed initial ne couvre que les 9 jours fériés FIXES marocains.
    MULTI-TENANT : chaque ligne appartient à UNE société.
    """

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: tenant (societe)
        related_name='notif_holidays',
        verbose_name='Société')
    date = models.DateField(verbose_name='Date')
    nom = models.CharField(max_length=150, verbose_name='Nom')
    recurrent_annuel = models.BooleanField(
        default=False,
        verbose_name='Récurrent chaque année')
    # HOLIDAY-PAYS (complément NTI18N13) — additif, défaut ``MA`` (même
    # patron/casse que `authentication.Company.pays`, SOL8) : TOUTES les
    # lignes existantes (calendrier marocain) restent ``MA``, donc AUCUN
    # comportement ne change tant qu'un appelant ne demande pas
    # explicitement à filtrer par pays (`calendar_utils.feries_entre`).
    pays = models.CharField(
        'Pays (ISO 3166-1 alpha-2)', max_length=2, default='MA',
        help_text='Code pays ISO du jour férié (MA = Maroc).')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Jour férié'
        verbose_name_plural = 'Jours fériés'
        ordering = ['date']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'date', 'nom'],
                name='notif_holiday_company_date_nom_uniq',
            ),
        ]

    def __str__(self):
        flag = ' (annuel)' if self.recurrent_annuel else ''
        return f'{self.date} — {self.nom}{flag}'


# =============================================================================
# QJ23 — WhatsApp BSP scaffold (flag-gated, défaut manuel wa.me)
# =============================================================================

class WhatsAppTemplate(TenantModel):
    """Registre des gabarits BSP WhatsApp approuvés par Meta, par entreprise.

    ADDITIF : sans aucune ligne, le comportement actuel (wa.me manuel) est
    préservé à 100 %. Ce modèle ne remplace PAS `parametres.MessageTemplate`
    (messages éditables manuels) — il ajoute le registre BSP (gabarits approuvés
    côté Meta, avec leur nom et leur langue).

    MULTI-TENANT : `company` est forcé côté serveur, jamais accepté du corps.
    Ne jamais exposer prix_achat / marge dans un message.

    ARC1 — pilote de conversion vers ``core.models.TenantModel`` : la FK
    ``company`` + les timestamps ``created_at``/``updated_at`` viennent désormais
    du socle. Le champ ``company`` est REDÉCLARÉ ci-dessous à l'IDENTIQUE pour
    préserver l'accesseur inverse historique (``company.whatsapp_bsp_templates``)
    — jamais un renommage. Migration générée vide (champs résolus inchangés).
    """

    # Redéclaré à l'identique (ARC1) : conserve le related_name historique.
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: tenant (societe)
        related_name='whatsapp_bsp_templates')
    # Nom du gabarit tel qu'approuvé par Meta (ex. 'devis_envoye_v1').
    name = models.CharField(max_length=100, verbose_name='Nom du gabarit Meta')
    # Corps du message en français (texte de référence interne — le texte réel
    # est côté Meta ; ici c'est un aide-mémoire éditable).
    body_fr = models.TextField(blank=True, default='', verbose_name='Corps FR (aide-mémoire)')
    # Code langue IETF (ex. 'fr', 'ar', 'fr_MA') — défaut FR.
    language = models.CharField(max_length=10, default='fr', verbose_name='Langue')
    active = models.BooleanField(default=True, verbose_name='Actif')

    # ── XMKT25 — Cycle d'approbation Meta ───────────────────────────────────
    class StatutApprobation(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        SOUMIS = 'soumis', 'Soumis'
        APPROUVE = 'approuve', 'Approuvé'
        REJETE = 'rejete', 'Rejeté'

    class Categorie(models.TextChoices):
        MARKETING = 'marketing', 'Marketing'
        UTILITY = 'utility', 'Utilitaire'

    statut_approbation = models.CharField(
        max_length=12, choices=StatutApprobation.choices,
        default=StatutApprobation.BROUILLON,
        verbose_name="Statut d'approbation Meta")
    # Motif de rejet éventuel (renseigné manuellement ou via la réponse Meta).
    motif_rejet = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Motif de rejet')
    categorie = models.CharField(
        max_length=12, choices=Categorie.choices, default=Categorie.UTILITY,
        verbose_name='Catégorie Meta')
    # Regroupe les variantes de langue d'un même gabarit logique (ex. fr/ar du
    # même nom) sans dépendre du nom Meta seul. Vide = pas de groupe explicite
    # (comportement actuel préservé).
    groupe = models.CharField(
        max_length=100, blank=True, default='', verbose_name='Groupe de variantes')
    # ARC1 — created_at / updated_at hérités de TenantModel (à l'identique).

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
            models.Index(fields=['company', 'active'], name='nwa_tpl_company_active_idx'),
            models.Index(
                fields=['company', 'statut_approbation'],
                name='nwa_tpl_company_statut_idx'),
        ]

    def __str__(self):
        return f'{self.company_id}:{self.name}:{self.language}'

    @property
    def is_approuve(self):
        return self.statut_approbation == self.StatutApprobation.APPROUVE


class WhatsAppMessageLog(TenantModel):
    """Journal des messages WhatsApp (envois BSP + liens manuels wa.me).

    Chaque tentative d'envoi ou de construction de lien wa.me peut laisser
    une trace ici. Les mises à jour de statut (livré/lu) arrivent via le
    webhook BSP et mettent à jour la ligne correspondante via `external_id`.

    MULTI-TENANT : `company` forcé côté serveur.
    Ne jamais stocker prix_achat / marge dans `body`.

    ARC1 — pilote de conversion vers ``core.models.TenantModel`` : FK ``company``
    + ``created_at``/``updated_at`` fournis par le socle. ``company`` REDÉCLARÉ à
    l'identique pour préserver l'accesseur ``company.whatsapp_message_logs``.
    Migration générée vide (champs résolus inchangés).
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
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: tenant (societe)
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
    # XMKT10 — id opaque de la ``marketing.Campagne`` d'origine (jamais un FK
    # direct : ``notifications`` est un satellite, il n'importe pas
    # ``apps.marketing``). NULL = message hors campagne (comportement
    # historique : notifications transactionnelles / liens manuels).
    campagne_id = models.PositiveIntegerField(
        null=True, blank=True, db_index=True,
        verbose_name='Id de la campagne (opaque)')
    # ARC1 — created_at / updated_at hérités de TenantModel (à l'identique).

    class Meta:
        verbose_name = 'Journal WhatsApp'
        verbose_name_plural = 'Journal WhatsApp'
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(
                fields=['company', 'recipient', 'status'],
                name='nwa_log_company_recip_st_idx',
            ),
            models.Index(
                fields=['company', 'created_at'],
                name='nwa_log_company_created_idx',
            ),
            models.Index(
                fields=['company', 'campagne_id'],
                name='nwa_log_company_campagne_idx',
            ),
        ]

    def __str__(self):
        return f'WA:{self.provider}:{self.status} → {self.recipient}'


# =============================================================================
# XKB5 — Annonces internes ciblées et programmées.
# =============================================================================

class Annonce(TenantModel):
    """Annonce interne, publiée à l'heure dite, ciblée département/rôle/tous.

    ADDITIF : nouvelle app, nouveau modèle. Une annonce non publiée n'a AUCUN
    effet (pas de notification, pas d'affichage dashboard). La publication est
    déclenchée par `sweep_daily` (Celery beat existant) quand
    `date_publication <= maintenant` et `publiee=False`. Elle expire seule (le
    front n'affiche plus une annonce dont `date_expiration` est dépassée) —
    aucun job de suppression n'est nécessaire.

    MULTI-TENANT : `company` posée côté serveur, jamais depuis le corps.

    ARC1 — pilote de conversion vers ``core.models.TenantModel`` : FK ``company``
    + ``created_at``/``updated_at`` fournis par le socle. ``company`` REDÉCLARÉ à
    l'identique pour préserver l'accesseur ``company.annonces``. Migration
    générée vide (champs résolus inchangés).
    """

    class Cible(models.TextChoices):
        TOUS = 'tous', 'Toute la société'
        ROLE = 'role', 'Par rôle'
        DEPARTEMENT = 'departement', 'Par département'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: tenant (societe)
        related_name='annonces', verbose_name='Société')
    titre = models.CharField(max_length=200, verbose_name='Titre')
    corps = models.TextField(blank=True, default='', verbose_name='Corps')
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='annonces_creees',
        verbose_name='Auteur')

    cible_type = models.CharField(
        max_length=15, choices=Cible.choices, default=Cible.TOUS,
        verbose_name='Type de ciblage')
    # Utilisé quand cible_type == ROLE (valeurs de CustomUser.role_legacy).
    cible_role = models.CharField(
        max_length=20, blank=True, default='', verbose_name='Rôle cible')
    # Utilisé quand cible_type == DEPARTEMENT — nom du département. SOLMVP19 :
    # la source de vérité (l'app rh, qui portait les départements) est sortie
    # du produit ; le choix reste au schéma (pas de migration dans cette lane)
    # mais `services.annonce_recipients` ne résout plus personne pour ce
    # ciblage (voir sa docstring).
    cible_departement_nom = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Département cible')

    # Programmation : publiée automatiquement quand date_publication est
    # atteinte (sweep quotidien). NULL = publication immédiate (dès création,
    # gérée côté service/vue — le modèle ne décide rien seul).
    date_publication = models.DateTimeField(
        null=True, blank=True, verbose_name='Publier le')
    date_expiration = models.DateTimeField(
        null=True, blank=True, verbose_name='Expire le')
    publiee = models.BooleanField(default=False, verbose_name='Publiée')
    date_publication_effective = models.DateTimeField(
        null=True, blank=True, verbose_name='Publiée le (effectif)')

    # Épinglée en tête du dashboard jusqu'à expiration.
    epinglee = models.BooleanField(default=False, verbose_name='Épinglée')

    # XKB6 — accusé de lecture obligatoire.
    lecture_obligatoire = models.BooleanField(
        default=False, verbose_name='Lecture obligatoire')

    # ARC1 — created_at / updated_at hérités de TenantModel (à l'identique).

    class Meta:
        verbose_name = 'Annonce'
        verbose_name_plural = 'Annonces'
        ordering = ['-epinglee', '-date_publication_effective', '-created_at']
        indexes = [
            models.Index(fields=['company', 'publiee']),
            models.Index(fields=['company', 'date_publication']),
            models.Index(fields=['company', 'epinglee']),
        ]

    def __str__(self):
        return self.titre

    def is_expiree(self, now=None):
        if not self.date_expiration:
            return False
        from django.utils import timezone as dj_timezone
        now = now or dj_timezone.now()
        return self.date_expiration <= now

    def is_due(self, now=None):
        """Prête à être publiée : programmée, pas déjà publiée, heure atteinte."""
        if self.publiee or not self.date_publication:
            return False
        from django.utils import timezone as dj_timezone
        now = now or dj_timezone.now()
        return self.date_publication <= now


class AnnonceLecture(models.Model):
    """XKB6 — Accusé de lecture obligatoire d'une annonce, par destinataire.

    Une ligne = un destinataire a cliqué « J'ai lu et compris » pour une
    annonce donnée. ADDITIF : l'absence de ligne = non lu (pas de blocage
    fonctionnel, seulement du reporting + relance)."""

    annonce = models.ForeignKey(
        Annonce, on_delete=models.CASCADE, related_name='lectures')  # on_delete: composition (parent-enfant)
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: tenant (societe)
        related_name='annonce_lectures')
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,  # on_delete: composition (utilisateur)
        related_name='annonce_lectures')
    date_lecture = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Accusé de lecture'
        verbose_name_plural = 'Accusés de lecture'
        ordering = ['-date_lecture']
        constraints = [
            models.UniqueConstraint(
                fields=['annonce', 'utilisateur'],
                name='notif_annonce_lecture_uniq',
            ),
        ]
        indexes = [
            models.Index(fields=['company', 'annonce']),
        ]

    def __str__(self):
        return f'{self.annonce_id}:{self.utilisateur_id}'


class AnnonceRelance(models.Model):
    """XKB6 — État de relance PAR DESTINATAIRE N'AYANT PAS ENCORE CONFIRMÉ.

    Distinct de `AnnonceLecture` (qui ne doit exister QUE pour une lecture
    réellement confirmée) : cette table suit uniquement l'idempotence des
    relances envoyées à qui n'a PAS (encore) cliqué « J'ai lu ». Une ligne ici
    ne signifie jamais une lecture confirmée."""

    annonce = models.ForeignKey(
        Annonce, on_delete=models.CASCADE, related_name='relances')  # on_delete: composition (parent-enfant)
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: tenant (societe)
        related_name='annonce_relances')
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,  # on_delete: composition (utilisateur)
        related_name='annonce_relances')
    relances_envoyees = models.PositiveSmallIntegerField(default=0)
    derniere_relance_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Relance de lecture'
        verbose_name_plural = 'Relances de lecture'
        ordering = ['-derniere_relance_le']
        constraints = [
            models.UniqueConstraint(
                fields=['annonce', 'utilisateur'],
                name='notif_annonce_relance_uniq',
            ),
        ]
        indexes = [
            models.Index(fields=['company', 'annonce']),
        ]

    def __str__(self):
        return f'relance {self.annonce_id}:{self.utilisateur_id}'


# =============================================================================
# YEVNT9 — Relance/escalade des approbations en attente.
# =============================================================================

class ApprovalReminderConfig(models.Model):
    """YEVNT9 — Seuils (en jours ouvrés) de relance/escalade des approbations
    en attente, par société. Singleton par société.

    ADDITIF : sans ligne, les helpers du sweep retombent sur les défauts de
    classe (2 jours ouvrés pour la relance, 6 pour l'escalade admin — un
    écart net entre les deux paliers : 4 était trop proche de la relance et
    pouvait se déclencher dès J+5 calendaires selon le jour de la semaine)."""

    DEFAULT_RELANCE_DAYS = 2
    DEFAULT_ESCALADE_DAYS = 6

    company = models.OneToOneField(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: tenant (societe)
        related_name='approval_reminder_config', verbose_name='Société')
    relance_days = models.PositiveSmallIntegerField(
        default=DEFAULT_RELANCE_DAYS,
        verbose_name='Seuil relance (jours ouvrés)')
    escalade_days = models.PositiveSmallIntegerField(
        default=DEFAULT_ESCALADE_DAYS,
        verbose_name='Seuil escalade admin (jours ouvrés)')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuration relance approbations'
        verbose_name_plural = 'Configurations relance approbations'

    def __str__(self):
        return f'ApprovalReminderConfig[{self.company_id}]'


class ApprovalReminderState(models.Model):
    """YEVNT9 — État de relance/escalade PAR approbation en attente (générique,
    couvre `automation.AutomationApproval` via content-type — jamais un FK
    dur vers l'app. SOLMVP19 : le second moteur historique, compta, est sorti
    du produit avec l'app compta.

    `palier` : 0 = jamais relancé, 1 = relance envoyée à l'approbateur,
    2 = escaladé à l'admin/owner-tier. Une ligne par approbation en attente ;
    supprimée/ignorée une fois la décision prise (le sweep ne la retrouve
    plus dans la requête « en attente » de son moteur)."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: tenant (societe)
        related_name='approval_reminder_states')
    content_type = models.ForeignKey(
        'contenttypes.ContentType', on_delete=models.CASCADE)  # on_delete: composition (parent-enfant)
    object_id = models.PositiveIntegerField()
    palier = models.PositiveSmallIntegerField(default=0)
    derniere_action_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'État de relance approbation'
        verbose_name_plural = 'États de relance approbation'
        ordering = ['-derniere_action_le']
        constraints = [
            models.UniqueConstraint(
                fields=['content_type', 'object_id'],
                name='notif_approval_reminder_state_uniq',
            ),
        ]
        indexes = [
            models.Index(fields=['company', 'content_type']),
        ]

    def __str__(self):
        return f'relance approbation {self.content_type_id}:{self.object_id} (palier {self.palier})'


# =============================================================================
# VX210(b) — snooze GÉNÉRIQUE d'un item d'approbation depuis « Ma file ».
# =============================================================================

class SnoozedItem(TenantModel):
    """VX210(b) — snooze d'un item HÉTÉROGÈNE de l'agrégateur d'approbations
    (``reporting.approbations``, 5 sources : automation/contrats/ged/
    installations/workflow) depuis « Ma file ». `records.Activity` a déjà son
    propre ``snoozed_until`` (VX85) — cette table couvre tout le RESTE (une
    approbation/facture n'a pas de ligne ``Activity`` à elle).

    Clé ``(source, object_id)`` — la MÊME convention textuelle déjà utilisée
    par tout l'agrégateur (``{source, id}``, ``_decider_approbation_core``),
    plutôt qu'un ``ContentType`` Django : évite d'importer les modèles des 5
    sources ici (frontière cross-app, CLAUDE.md). Une ligne = masqué pour CE
    ``user`` jusqu'à ``snoozed_until`` (jour inclus) ; supprimée au réveil
    (sweep ``reveiller_snoozes``), jamais accumulée."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: tenant (societe)
        related_name='snoozed_items')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,  # on_delete: composition (utilisateur)
        related_name='snoozed_items')
    source = models.CharField(max_length=20)
    object_id = models.PositiveIntegerField()
    snoozed_until = models.DateField()

    class Meta:
        verbose_name = 'Item reporté (snooze, VX210)'
        verbose_name_plural = 'Items reportés (snooze, VX210)'
        ordering = ['-created_at']
        # PAS d'index secondaire explicite ici (table petite — une ligne par
        # snooze actif — et les noms d'index Django hashés ne peuvent pas
        # être reproduits à la main sans `makemigrations` ; voir la note
        # « migration_index_name_divergence » : mieux vaut aucun index que
        # divergence nom-hasard/migration). La contrainte d'unicité suffit
        # comme index de recherche `(user, source, object_id)`.
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'source', 'object_id'],
                name='notif_snoozed_item_user_source_obj_uniq',
            ),
        ]

    def __str__(self):
        return f'snooze {self.source}:{self.object_id} → {self.user_id}'


# =============================================================================
# MSGACC1 — Message d'accueil : posé par un responsable/admin pour UN employé
# précis, affiché EN PLEIN ÉCRAN à sa PREMIÈRE ouverture de l'ERP à partir
# d'une heure choisie.
# =============================================================================

class MessageAccueil(TenantModel):
    """MSGACC1 — message d'accueil (bonjour/consigne) ciblant un destinataire.

    CE N'EST PAS UNE NOTIFICATION (règle fondateur) : aucun ``EventType``,
    aucune ligne dans le centre de notifications, aucun push. Uniquement la
    modale d'accueil, câblée côté frontend sur ``a-lire``.

    Visibilité : le destinataire le voit à sa PREMIÈRE ouverture de l'ERP à
    partir de ``visible_a_partir_de`` (choisi 8h00, ouvre à 8h40 → il le voit ;
    ouvert à 7h50 → rien). Tant que ``lu_le`` est vide, la modale se
    représente à chaque ouverture.

    MULTI-TENANT : ``company`` posée côté serveur (jamais depuis le corps).
    ``destinataire`` CASCADE (le message n'a plus de sens sans son
    destinataire) ; ``auteur`` SET_NULL (perdre la trace de qui a écrit ne
    doit jamais empêcher la suppression d'un compte — le frontend affiche
    « Direction » à défaut d'auteur)."""

    # ``company`` + ``created_at``/``updated_at`` hérités de TenantModel
    # (SCA4 — jamais la paire multi-société re-hand-rollée).
    destinataire = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,  # on_delete: composition (utilisateur)
        related_name='messages_accueil_recus', verbose_name='Destinataire')
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='messages_accueil_envoyes',
        verbose_name='Auteur')
    visible_a_partir_de = models.DateTimeField(
        db_index=True, verbose_name='Visible à partir de')
    corps = models.TextField(verbose_name='Corps')
    lu_le = models.DateTimeField(null=True, blank=True, verbose_name='Lu le')

    class Meta:
        verbose_name = "Message d'accueil"
        verbose_name_plural = "Messages d'accueil"
        ordering = ['visible_a_partir_de', 'id']
        indexes = [
            models.Index(
                fields=['company', 'destinataire', 'lu_le'],
                name='notif_msgacc_dest_lu_idx'),
            models.Index(
                fields=['company', 'auteur'], name='notif_msgacc_auteur_idx'),
        ]

    def __str__(self):
        return f'MessageAccueil → {self.destinataire_id} ({self.visible_a_partir_de})'
