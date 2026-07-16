"""Journal d'activité — modèle d'audit unique, company-scopé (Feature G).

UN seul modèle générique (content type + object id + snapshot du libellé)
enregistre TOUTES les actions internes : connexions, CRUD sur les objets
métier, et actions clés (PDF, envoi, export, acceptation/refus, changement de
statut). La capture est best-effort et ne bloque JAMAIS la requête (voir
``recorder.record``). Interne / réservé au Directeur — le détail complet est
permis ici (jamais sur un document client). Tous les horodatages sont en UTC en
base ; le bucketing se fait en Africa/Casablanca à la lecture (voir ``views``).
"""
import hashlib

from django.conf import settings
from django.db import models


def compute_entry_hash(*, prev_hash, company_id, action, actor_username,
                       object_id, object_repr, detail, timestamp):
    """Hash SHA-256 d'inviolabilité d'une ligne d'audit (NTSEC17).

    Chaîne le hash de la ligne précédente (``prev_hash``) avec le contenu
    canonique de la ligne. Toute altération d'un champ chaîné change le hash
    et casse la vérification de chaîne en aval."""
    canonical = '|'.join([
        prev_hash or '',
        str(company_id or ''),
        str(action or ''),
        str(actor_username or ''),
        str(object_id or ''),
        str(object_repr or ''),
        str(detail or ''),
        timestamp.isoformat() if timestamp else '',
    ])
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


class AuditLog(models.Model):
    class Action(models.TextChoices):
        CREATE = 'create', 'Création'
        UPDATE = 'update', 'Modification'
        DELETE = 'delete', 'Suppression'
        STATUS = 'status', 'Changement de statut'
        LOGIN = 'login', 'Connexion'
        LOGOUT = 'logout', 'Déconnexion'
        LOGIN_FAILED = 'login_failed', 'Échec de connexion'
        # FG23 — alerte de sécurité (ex. trop d'échecs consécutifs → verrou).
        SECURITY_ALERT = 'security_alert', 'Alerte de sécurité'
        PDF = 'pdf', 'PDF généré'
        EMAIL = 'email', 'Email envoyé'
        WHATSAPP = 'whatsapp', 'WhatsApp envoyé'
        EXPORT = 'export', 'Export'
        ACCEPT = 'accept', 'Devis accepté'
        REFUSE = 'refuse', 'Devis refusé'
        # YEVNT5 — notification in-app émise (notifications.notify()).
        NOTIFY = 'notify', 'Notification envoyée'
        # XPLT19 — bascule de société active (utilisateur multi-sociétés).
        SWITCH_COMPANY = 'switch_company', 'Changement de société active'

    # Société forcée côté serveur (jamais depuis le corps de requête). Nullable
    # pour les évènements sans société connue (échec de connexion avant auth).
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='audit_logs',
    )
    # Acteur ; NULL = action système (webhook, tâche) ou connexion échouée.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='audit_logs',
    )
    # Instantané du nom d'utilisateur (acteur, ou username tenté à l'échec de
    # connexion) — survit à la suppression du compte.
    actor_username = models.CharField(max_length=150, blank=True, default='')
    action = models.CharField(
        max_length=20, choices=Action.choices, db_index=True)
    # Cible : content type + id + libellé instantané (lien retour si l'objet
    # existe encore). content_type NULL pour les évènements sans objet (login).
    content_type = models.ForeignKey(
        'contenttypes.ContentType',
        on_delete=models.SET_NULL,
        null=True, blank=True,
    )
    object_id = models.CharField(max_length=64, blank=True, default='')
    object_repr = models.CharField(max_length=255, blank=True, default='')
    # Court « ce qui a changé » (ex. « Statut : Brouillon → Envoyé »).
    detail = models.TextField(blank=True, default='')
    # YHARD3 — diff structuré best-effort, additif : liste JSON
    # ``[{"field": ..., "old": ..., "new": ...}, ...]``. Nullable/absent pour
    # tout le legacy et pour les actions non-UPDATE — la reconstruction as-of
    # dégrade proprement (voir ``selectors.reconstruct_as_of``, fallback parse
    # de ``detail``). Rempli best-effort par ``recorder.record`` ; ne bloque
    # jamais la requête.
    changes = models.JSONField('Diff structuré', null=True, blank=True)
    # NTSEC17 — chaînage d'inviolabilité (hash-chaining) par société. Chaque
    # ligne porte le hash de la précédente (``prev_hash``) et son propre hash
    # (``entry_hash``), calculés best-effort au ``record()``. Vides pour le
    # legacy : la vérification de chaîne démarre à la première ligne chaînée.
    prev_hash = models.CharField(max_length=64, blank=True, default='')
    entry_hash = models.CharField(
        max_length=64, blank=True, default='', db_index=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Entrée du journal d'activité"
        verbose_name_plural = "Journal d'activité"
        indexes = [
            models.Index(fields=['company', '-timestamp']),
            models.Index(fields=['company', 'action', '-timestamp']),
            models.Index(fields=['content_type', 'object_id']),
        ]

    def __str__(self):
        return f'{self.action} {self.object_repr} @ {self.timestamp:%Y-%m-%d %H:%M}'
