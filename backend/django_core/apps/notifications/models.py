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

from core.models import TenantModel

logger = logging.getLogger(__name__)


class EventType(models.TextChoices):
    """Événements métier déclencheurs de notification (clé EN, libellé FR)."""
    LEAD_ASSIGNED = 'lead_assigned', 'Nouveau lead assigné'
    # QJ2 — speed-to-lead : nouveau lead entrant (webhook site web).
    LEAD_NEW = 'lead_new', 'Nouveau lead site web'
    DEVIS_ACCEPTED = 'devis_accepted', 'Devis accepté'
    # QJ2 — première ouverture du lien de proposition par le client.
    DEVIS_OPENED = 'devis_opened', 'Proposition ouverte par le client'
    # QX36 — le client RÉPOND par email à une proposition/facture (réponse
    # rattachée au devis via sa référence) : le vendeur est notifié.
    DEVIS_REPLY = 'devis_reply', 'Réponse email du client sur un devis'
    # QX13 — une relance de devis (cadence j+2/j+5/j+10) est DUE : notification
    # in-app au vendeur avec brouillon wa.me + lien proposition prêts.
    DEVIS_NUDGE_DUE = 'devis_nudge_due', 'Relance de devis à faire'
    # QX31be — un lead CHAUD (score élevé) dont la notif d'arrivée reste NON LUE
    # après N minutes : escalade speed-to-lead (21× de qualification si contact
    # < 5 min). Notifie les managers en plus du destinataire initial.
    HOT_LEAD_UNREAD = 'hot_lead_unread', 'Lead chaud non contacté (escalade)'
    # QJ27 — le client demande à être contacté (depuis la proposition publique).
    CLIENT_CONTACT_REQUEST = (
        'client_contact_request', 'Client souhaite être contacté')
    # QJ28 — un vendeur demande l'avis de son supérieur sur un devis.
    DEVIS_SUPERIOR_CONTACT_REQUESTED = (
        'devis_superior_contact_requested',
        'Avis du supérieur demandé sur un devis')
    # QW4 — un lead demande explicitement un RAPPEL téléphonique (distinct
    # d'une simple réponse WhatsApp) : notification à urgence plus élevée.
    LEAD_CALLBACK_REQUESTED = (
        'lead_callback_requested', 'Rappel téléphonique demandé')
    # QW4 — le rappel demandé n'a pas été actionné dans le SLA serré (moitié
    # du SLA générique premier contact) : escalade dédiée.
    LEAD_CALLBACK_SLA_BREACH = (
        'lead_callback_sla_breach', 'Rappel demandé non actionné (SLA)')
    CHANTIER_DUE = 'chantier_due', 'Chantier à installer'
    FACTURE_OVERDUE = 'facture_overdue', 'Facture en retard'
    WARRANTY_EXPIRING = 'warranty_expiring', 'Garantie bientôt expirée'
    MAINTENANCE_DUE = 'maintenance_due', 'Visite de maintenance due'
    STOCK_LOW = 'stock_low', 'Stock bas'
    # ZSTK2 — un lot/réception approche de sa date de péremption (fenêtre
    # configurable par société, cron quotidien).
    STOCK_EXPIRATION_SOON = (
        'stock_expiration_soon', 'Lot bientôt périmé')
    SAV_TICKET_OPENED = 'sav_ticket_opened', 'Ticket SAV ouvert'
    SAV_TICKET_BREACHING = 'sav_ticket_breaching', 'Ticket SAV proche de son délai'
    # ZSAV3 — activité planifiée à échéance sur un ticket SAV (échue, pas faite).
    SAV_ACTIVITE_DUE = 'sav_activite_due', 'Activité SAV à échéance'
    # ZSAV9 — notification d'un suiveur de ticket (note ou transition).
    SAV_TICKET_FOLLOWED_UPDATE = (
        'sav_ticket_followed_update', 'Mise à jour sur un ticket suivi')
    # YSERV5 — génération automatique nocturne de visites préventives dues.
    SAV_VISITES_AUTO_GENEREES = (
        'sav_visites_auto_generees', 'Visites préventives générées automatiquement')
    # Group S — messagerie interne (« Discuss »).
    CHAT_MESSAGE = 'chat_message', 'Nouveau message'
    CHAT_MENTION = 'chat_mention', 'Vous avez été mentionné'
    DIGEST = 'digest', 'Récapitulatif'
    # XKB5 — annonce interne publiée (programmée ou immédiate).
    ANNONCE_PUBLISHED = 'annonce_published', 'Nouvelle annonce interne'
    # XKB6 — relance de lecture obligatoire non confirmée.
    ANNONCE_READ_REMINDER = (
        'annonce_read_reminder', 'Relance lecture obligatoire')
    # YEVNT8 — demandes d'approbation (automation N73 + compta FG213).
    APPROVAL_REQUESTED = 'approval_requested', "Approbation demandée"
    APPROVAL_DECIDED = 'approval_decided', "Approbation décidée"
    # YEVNT9 — relance/escalade d'une approbation restée en attente.
    APPROVAL_REMINDER = 'approval_reminder', "Relance d'approbation"
    APPROVAL_ESCALATED = 'approval_escalated', "Approbation escaladée"
    # XPUR1 — document de conformité fournisseur (ARF/CNSS/RC/assurance)
    # expiré ou bientôt expiré.
    SUPPLIER_DOC_EXPIRING = (
        'supplier_doc_expiring', 'Document fournisseur bientôt expiré')
    # XPUR7 — BCF envoyé en retard (prévue/confirmée dépassée, non reçu).
    BCF_LATE = 'bcf_late', 'Bon de commande fournisseur en retard'
    # YPROC7 — un BCF est annulé (cascade sur ses réceptions brouillon).
    BCF_CANCELLED = 'bcf_cancelled', 'Bon de commande fournisseur annulé'
    # ZPUR7 — brouillon de relance PROPOSÉ (jamais envoyé) pour un BCF en
    # retard, distinct de BCF_LATE (l'alerte buyer XPUR7) : jamais de
    # doublon de notification.
    BCF_RELANCE_PROPOSEE = (
        'bcf_relance_proposee', 'Brouillon de relance BCF proposé')
    # XPRJ22 — retard/risque de planning sur un projet (gestion_projet).
    PROJET_RETARD = 'projet_retard', 'Retard planning projet'
    # XFLT18 — dépassement de budget flotte annuel (par catégorie de coût).
    FLOTTE_BUDGET_DEPASSEMENT = (
        'flotte_budget_depassement', 'Dépassement budget flotte')
    # XFLT24 — géofencing : entrée en zone interdite / mouvement hors plage
    # horaire autorisée, détecté sur les relevés télématiques déjà ingérés.
    FLOTTE_ZONE_ALERTE = (
        'flotte_zone_alerte', 'Alerte géofencing véhicule')
    # XFLT25 — code défaut moteur (DTC) critique détecté sur un relevé
    # télématique (manuel ou fournisseur).
    FLOTTE_DTC_CRITIQUE = (
        'flotte_dtc_critique', 'Code défaut moteur critique (DTC)')
    # ZGED14 — une demande de signature en attente approche de son expiration
    # (versant ÉMETTEUR, complète les relances SIGNATAIRE de XGED2).
    GED_SIGNATURE_EXPIRATION_PROCHE = (
        'ged_signature_expiration_proche',
        'Demande de signature bientôt expirée')
    # YEVNT2 — un devis envoyé a expiré automatiquement (QJ5, date de
    # validité dépassée) sans action du propriétaire.
    DEVIS_EXPIRED = 'devis_expired', 'Devis expiré'
    # YEVNT12 — un incident QHSE CRITIQUE est déclaré (au-delà de la note
    # chatter existante QHSE32) : notifie les responsables QHSE.
    INCIDENT_CRITICAL = 'incident_critical', 'Incident QHSE critique'
    # XMKT35 — un post réseau social planifié arrive à échéance SANS jeton
    # Meta Graph configuré : rappel manuel (texte prêt à coller) à l'auteur.
    POST_SOCIAL_RAPPEL = 'post_social_rappel', 'Post social à publier (rappel)'
    # YSERV11 — réponse NPS promoteur (9-10) : proposer le parrainage au
    # moment de l'enchantement (notification au commercial du client).
    NPS_PROMOTEUR = 'nps_promoteur', 'Client promoteur — proposer le parrainage'
    # ARC36 — une facture est intégralement réglée (résiduel→0, bus
    # ``facture_payee``) : notifie le vendeur (créateur de la facture).
    FACTURE_PAYEE = 'facture_payee', 'Facture intégralement réglée'
    # ARC36 — un bon de commande est créé depuis un devis accepté (bus
    # ``bon_commande_cree``) : notifie le magasinier/managers (routable par
    # ``NotificationRoutingRule`` vers l'utilisateur entrepôt).
    BON_COMMANDE_CREE = 'bon_commande_cree', 'Bon de commande créé'
    # ARC35 — consomme le seam ``contrat_signe`` (bus ``core.events``) :
    # notifie le créateur du contrat (repli managers) qu'un contrat vient
    # d'être intégralement signé.
    CONTRAT_SIGNE = 'contrat_signe', 'Contrat signé'
    # ARC37 — sav devient émetteur du bus (``core.events.ticket_resolu``) :
    # notifie le technicien assigné (repli managers) qu'un ticket est résolu.
    SAV_TICKET_RESOLU = 'sav_ticket_resolu', 'Ticket SAV résolu'
    # ARC37 — sav devient émetteur du bus
    # (``core.events.equipement_remplace``) : notifie les managers qu'un
    # équipement du parc a été remplacé suite à un retrait de pièce.
    SAV_EQUIPEMENT_REMPLACE = (
        'sav_equipement_remplace', 'Équipement SAV remplacé')
    # ARC37 — gestion_projet devient émetteur du bus
    # (``core.events.projet_status_change``) : notifie le responsable du
    # projet d'un changement de statut.
    PROJET_STATUT_CHANGE = 'projet_statut_change', 'Statut de projet modifié'
    # ARC39 — couverture notifications : le rapport O&M périodique
    # (``monitoring/report.py``) est un envoi CLIENT (PDF joint, reste un
    # ``EmailMessage`` direct — exception documentée comme
    # ``ventes/email_service.py``/``installations/rfq_service.py``) ; cet
    # événement notifie EN INTERNE les responsables qu'un rapport vient
    # d'être envoyé, pour que l'équipe O&M ait enfin une trace côté
    # notifications (jusqu'ici totalement invisible en interne).
    MONITORING_RAPPORT = 'monitoring_rapport', 'Rapport O&M envoyé au client'
    # ARC39 — ARC25 émettait déjà ``notify_many(..., 'paie_rib_divergence',
    # ...)`` sans que ce type soit enregistré (avertissement + notification
    # in-app jamais persistée). Enregistrement de l'événement existant, aucun
    # changement de comportement de l'appelant.
    PAIE_RIB_DIVERGENCE = (
        'paie_rib_divergence', 'Divergence RIB paie ↔ RH')
    # ARC39 — un run de paie (``PeriodePaie``) devient PRÊT (statut
    # ``validee`` : tous ses bulletins sont validés) : notifie les
    # gestionnaires paie que le run peut passer à la génération de l'ordre de
    # virement / la clôture.
    PAIE_RUN_PRET = 'paie_run_pret', 'Run de paie prêt (validé)'
    # VX213 — handoffs AVAL (exécution) longtemps muets. (a) un chantier est
    # créé depuis un devis accepté et assigné à un technicien ; (b) un chantier
    # est réassigné à un NOUVEAU technicien : dans les deux cas l'installateur
    # est notifié (le plus gros transfert de l'entreprise n'est plus silencieux).
    CHANTIER_ASSIGNE = 'chantier_assigne', 'Nouveau chantier assigné'
    # VX213 — le bord RETOUR d'une demande d'achat : à l'approbation OU au refus,
    # le DEMANDEUR (created_by) est notifié de la décision (motif si refus).
    DA_DECIDEE = 'da_decidee', "Demande d'achat décidée"
    # VX213 — SLA : une demande d'achat reste SOUMISE au-delà du seuil sans
    # décision → relance des approbateurs (miroir de sav_ticket_breaching).
    DA_SOUMISE_STALE = 'da_soumise_stale', "Demande d'achat en attente (SLA)"
    # VX210(a) — un item snoozé (``records.Activity`` VX85, ou une approbation
    # VX210(b) via ``SnoozedItem``) revient dans la file : notification
    # LÉGÈRE au propriétaire, jamais une nouvelle demande d'action.
    SNOOZE_REVEIL = 'snooze_reveil', '⏰ De retour'


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
        'authentication.Company', on_delete=models.CASCADE,
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
        'authentication.Company', on_delete=models.CASCADE,
        related_name='notif_holidays',
        verbose_name='Société')
    date = models.DateField(verbose_name='Date')
    nom = models.CharField(max_length=150, verbose_name='Nom')
    recurrent_annuel = models.BooleanField(
        default=False,
        verbose_name='Récurrent chaque année')
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
        'authentication.Company', on_delete=models.CASCADE,
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
    # Utilisé quand cible_type == DEPARTEMENT — nom du département
    # (`rh.Departement.nom`), comparé en lecture seule via un import
    # function-local (jamais un FK cross-app dur, cf. CLAUDE.md).
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
        Annonce, on_delete=models.CASCADE, related_name='lectures')
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='annonce_lectures')
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
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
        Annonce, on_delete=models.CASCADE, related_name='relances')
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='annonce_relances')
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
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
        'authentication.Company', on_delete=models.CASCADE,
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
    couvre `automation.AutomationApproval` ET `compta.DemandeApprobationConfig`
    via content-type — mêmes deux moteurs que YEVNT8, jamais un FK dur vers
    l'une ou l'autre app).

    `palier` : 0 = jamais relancé, 1 = relance envoyée à l'approbateur,
    2 = escaladé à l'admin/owner-tier. Une ligne par approbation en attente ;
    supprimée/ignorée une fois la décision prise (le sweep ne la retrouve
    plus dans la requête « en attente » de son moteur)."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='approval_reminder_states')
    content_type = models.ForeignKey(
        'contenttypes.ContentType', on_delete=models.CASCADE)
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
        'authentication.Company', on_delete=models.CASCADE,
        related_name='snoozed_items')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
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
