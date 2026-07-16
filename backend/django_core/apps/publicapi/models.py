"""Modèles de l'API publique (N89).

- ApiKey : clé d'API rattachée à une société, avec scopes de lecture. Seul un
  HASH de la clé est stocké ; la clé en clair n'est montrée qu'une seule fois,
  à la création.
- Webhook : abonnement sortant signé (HMAC-SHA256) à des évènements métier.
- WebhookDelivery : journal best-effort des tentatives de livraison.

Additif uniquement : nouveaux modèles, FK company obligatoire, aucune
migration destructive.
"""
import hashlib
import hmac
import secrets

from django.conf import settings
from django.db import models

from core.crypto_fields import EncryptedCharField

from .constants import SCOPE_CHOICES, EVENT_CHOICES


# Préfixe lisible de toute clé émise (aide au repérage côté client/logs).
API_KEY_PREFIX = 'tqk_'
# Longueur de la part visible (préfixe inclus) stockée en clair pour identifier
# une clé sans jamais révéler le secret complet.
VISIBLE_PREFIX_LEN = 12


def hash_key(raw_key):
    """Empreinte déterministe d'une clé d'API — c'est ce qui est stocké/comparé.

    Une clé d'API est un secret À HAUTE ENTROPIE (`secrets.token_urlsafe(32)`,
    256 bits), pas un mot de passe humain : un hash lent (bcrypt/argon2) est
    inutile et casserait la résolution O(1) par empreinte. On utilise donc un
    HMAC-SHA256 « poivré » par la SECRET_KEY du serveur : déterministe (donc
    indexable/recherche directe) tout en rendant une fuite de la table
    d'empreintes inexploitable hors-ligne sans le secret serveur.
    """
    return hmac.new(
        settings.SECRET_KEY.encode('utf-8'),
        raw_key.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()


def generate_raw_key():
    """Génère une nouvelle clé en clair (préfixe + secret URL-safe)."""
    return API_KEY_PREFIX + secrets.token_urlsafe(32)


class ApiKey(models.Model):
    """Clé d'API d'une société. Stocke le HASH, jamais le secret en clair."""

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='api_keys',
    )
    label = models.CharField(max_length=120)
    # Hash SHA-256 (hex) de la clé en clair — unique pour la résolution rapide.
    key_hash = models.CharField(max_length=64, unique=True, db_index=True)
    # Part visible (ex. « tqk_Ab12Cd34 ») affichée dans la liste des clés.
    prefix = models.CharField(max_length=20)
    # Scopes accordés à cette clé (sous-ensemble de constants.ALL_SCOPES).
    scopes = models.JSONField(default=list, blank=True)
    enabled = models.BooleanField(default=True)
    # NTAPI5 — épingle la version d'API SERVIE à cette clé, indépendamment du
    # préfixe de chemin appelé (NTAPI1, pas encore construit) : une clé
    # épinglée 'v1' reste sur 'v1' même via un path non-versionné. Changer de
    # version est une action admin explicite (jamais automatique).
    api_version = models.CharField(max_length=10, default='v1', blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='api_keys_crees',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Clé API'
        verbose_name_plural = 'Clés API'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'enabled']),
        ]

    def __str__(self):
        return f'{self.label} ({self.prefix}…)'

    @classmethod
    def issue(cls, *, company, label, scopes, created_by=None):
        """Crée une clé et renvoie (instance, clé_en_clair).

        La clé en clair n'est disponible qu'ici, à la création — elle n'est
        jamais re-stockée. Seuls les scopes connus sont retenus.
        """
        from .constants import ALL_SCOPES
        raw_key = generate_raw_key()
        clean_scopes = [s for s in (scopes or []) if s in ALL_SCOPES]
        instance = cls.objects.create(
            company=company,
            label=label,
            key_hash=hash_key(raw_key),
            prefix=raw_key[:VISIBLE_PREFIX_LEN],
            scopes=clean_scopes,
            created_by=created_by,
        )
        return instance, raw_key

    def has_scope(self, scope):
        return scope in (self.scopes or [])


class Webhook(models.Model):
    """Abonnement webhook sortant d'une société. Le secret signe chaque envoi."""

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='webhooks',
    )
    label = models.CharField(max_length=120, blank=True, default='')
    target_url = models.URLField(max_length=500)
    # Secret partagé : sert à signer le corps en HMAC-SHA256. Généré côté
    # serveur ; renvoyé une fois à la création/rotation.
    secret = EncryptedCharField(max_length=128)
    # Évènements auxquels ce webhook est abonné (sous-ensemble de ALL_EVENTS).
    events = models.JSONField(default=list, blank=True)
    enabled = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='webhooks_crees',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Webhook'
        verbose_name_plural = 'Webhooks'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'enabled']),
        ]

    def __str__(self):
        return self.label or self.target_url

    @staticmethod
    def generate_secret():
        return secrets.token_urlsafe(32)

    def subscribes_to(self, event):
        return event in (self.events or [])


class WebhookDelivery(models.Model):
    """Journal best-effort d'une tentative de livraison de webhook."""

    class Statut(models.TextChoices):
        SUCCESS = 'success', 'Succès'
        FAILED = 'failed', 'Échec'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='webhook_deliveries',
    )
    webhook = models.ForeignKey(
        Webhook,
        on_delete=models.CASCADE,
        related_name='deliveries',
    )
    event = models.CharField(max_length=50)
    # YAPIC8 — identité STABLE de l'évènement (uuid4), partagée par toutes les
    # tentatives et réutilisée à l'identique par le replay (FG102). Vide pour
    # les livraisons historiques antérieures à YAPIC8.
    event_id = models.CharField(max_length=36, blank=True, default='',
                                db_index=True)
    # Charge utile envoyée (telle quelle) — pour rejouer/diagnostiquer.
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.FAILED)
    # Code HTTP renvoyé par la cible (NULL si la requête a échoué avant réponse).
    response_status = models.IntegerField(null=True, blank=True)
    error = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Livraison webhook'
        verbose_name_plural = 'Livraisons webhook'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'created_at']),
        ]

    def __str__(self):
        return f'{self.event} → {self.status}'


class IdempotencyRecord(models.Model):
    """XPLT5 — mémorise la réponse d'un appel d'ÉCRITURE de l'API publique
    pour un en-tête ``Idempotency-Key`` donné, scopé à (clé API, endpoint).

    Rejouer le MÊME couple (clé, endpoint, Idempotency-Key) avec un corps
    identique renvoie la réponse mémorisée SANS recréer l'objet ; avec un
    corps différent → 409 (conflit). Distinct du futur `core.IdempotencyRecord`
    générique (YAPIC9, POST internes JWT) — celui-ci ne couvre QUE l'API
    publique par clé, jamais les endpoints internes."""

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='publicapi_idempotency_records',
    )
    api_key = models.ForeignKey(
        ApiKey,
        on_delete=models.CASCADE,  # on_delete: un enregistrement d'idempotence n'existe que pour sa clé API
        related_name='idempotency_records',
    )
    endpoint = models.CharField(max_length=100)
    idempotency_key = models.CharField(max_length=255)
    # Empreinte du corps de requête (hash) — détecte un rejeu avec un corps
    # DIFFÉRENT sous la même clé d'idempotence (→ 409).
    request_fingerprint = models.CharField(max_length=64)
    response_status = models.IntegerField()
    response_body = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Enregistrement d'idempotence (API publique)"
        verbose_name_plural = "Enregistrements d'idempotence (API publique)"
        ordering = ['-created_at']
        unique_together = [('api_key', 'endpoint', 'idempotency_key')]
        indexes = [
            models.Index(fields=['company', 'created_at']),
        ]

    def __str__(self):
        return f'{self.endpoint}:{self.idempotency_key}'


# Re-export pour confort (utilisé par admin/serializers/tests).
__all__ = [
    'ApiKey', 'Webhook', 'WebhookDelivery', 'IdempotencyRecord',
    'hash_key', 'generate_raw_key',
    'API_KEY_PREFIX', 'SCOPE_CHOICES', 'EVENT_CHOICES',
]


class ServiceAccount(models.Model):
    """Compte de service (identité machine non-humaine) — NTSEC24.

    Authentifie une intégration interne / un script DISTINCT d'un ``CustomUser``
    humain : jamais de login UI, jamais de MFA, jamais de rôle humain. Ne porte
    que des SCOPES allowlistés (sous-ensemble de ``constants.ALL_SCOPES``, comme
    ``ApiKey``) et un jeton porteur haché émis une seule fois. Scopé société.
    """

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: tenant-cascade — un compte de service n'existe que pour sa société
        related_name='service_accounts')
    nom = models.CharField(max_length=120)
    scopes = models.JSONField(default=list, blank=True)
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    prefix = models.CharField(max_length=20, blank=True, default='')
    actif = models.BooleanField(default=True)
    expire_le = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='service_accounts_crees')
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Compte de service'
        verbose_name_plural = 'Comptes de service'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['company', 'actif'],
                                name='publicapi_svc_comp_actif_idx')]

    def __str__(self):
        return f'ServiceAccount({self.company_id}, {self.nom})'

    @property
    def est_actif(self):
        from django.utils import timezone
        if not self.actif:
            return False
        return self.expire_le is None or self.expire_le > timezone.now()

    def has_scope(self, scope):
        return scope in (self.scopes or [])

    @classmethod
    def issue(cls, *, company, nom, scopes, created_by=None, expire_le=None):
        """Crée un compte de service et renvoie ``(instance, jeton_en_clair)``.

        Réutilise le hachage/allowlist de scopes de ``ApiKey`` (jamais dupliqué).
        Le jeton en clair n'est disponible qu'ici — jamais re-stocké."""
        from .constants import ALL_SCOPES
        raw = generate_raw_key()
        clean = [s for s in (scopes or []) if s in ALL_SCOPES]
        inst = cls.objects.create(
            company=company, nom=nom, scopes=clean,
            token_hash=hash_key(raw), prefix=raw[:VISIBLE_PREFIX_LEN],
            created_by=created_by, expire_le=expire_le)
        return inst, raw

    def rotate(self):
        """Régénère le jeton (invalide l'ancien). Renvoie le nouveau clair."""
        raw = generate_raw_key()
        self.token_hash = hash_key(raw)
        self.prefix = raw[:VISIBLE_PREFIX_LEN]
        self.save(update_fields=['token_hash', 'prefix'])
        return raw


class WebhookDeliveryArchive(models.Model):
    """YOPSB11 — copie FROIDE d'une ``WebhookDelivery`` archivée.

    Le journal des livraisons (`WebhookDelivery`) est append-only et grossit
    sans borne (une ligne par tentative). La politique de rétention YOPSB11
    déplace les livraisons anciennes ici (par lots) puis les supprime de la
    table vive. Schéma miroir SANS index chaud, FK dénormalisées en
    identifiants entiers (aucune cascade sur l'archive)."""

    original_id = models.BigIntegerField(
        help_text="PK de la WebhookDelivery d'origine (table vive).")
    company_id = models.BigIntegerField(null=True, blank=True)
    webhook_id = models.BigIntegerField(null=True, blank=True)
    event = models.CharField(max_length=50)
    event_id = models.CharField(max_length=36, blank=True, default='')
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=10)
    response_status = models.IntegerField(null=True, blank=True)
    error = models.TextField(blank=True, default='')
    created_at = models.DateTimeField()
    archived_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Livraison webhook (archive)'
        verbose_name_plural = 'Livraisons webhook (archive)'

    def __str__(self):
        return f'archive:{self.original_id}'
