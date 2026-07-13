"""Modèles de la fondation Identité & accès.

NTSEC11 — Allowlist d'adresses IP / CIDR par société. Deux modèles :

* ``NetworkPolicy`` : la politique réseau d'UNE société (mode off/monitor/
  enforce, cible all/admins). Un enregistrement par société au maximum.
* ``IpAllowRule`` : une plage CIDR autorisée rattachée à la politique.

La politique est INERTE par défaut (``mode='off'``) : sans configuration
explicite, aucune requête n'est jamais bloquée ni journalisée. Le contrôle
runtime est porté par ``apps.identity.middleware.NetworkPolicyMiddleware``.
"""
import ipaddress

from django.core.exceptions import ValidationError
from django.db import models

from core.models import TenantModel


class NetworkPolicy(TenantModel):
    """Politique d'allowlist réseau d'une société (NTSEC11).

    ``mode`` :
      * ``off``     — inactif (défaut) : le middleware ne fait rien.
      * ``monitor`` — journalise une ``SECURITY_ALERT`` pour toute requête
        authentifiée hors plage, sans jamais bloquer.
      * ``enforce`` — refuse (403) toute requête authentifiée hors plage.

    ``applies_to`` :
      * ``all``    — la politique s'applique à tous les utilisateurs (défaut).
      * ``admins`` — elle ne s'applique qu'aux comptes administrateurs.
    """

    class Mode(models.TextChoices):
        OFF = 'off', 'Inactif'
        MONITOR = 'monitor', 'Surveillance'
        ENFORCE = 'enforce', 'Application'

    class AppliesTo(models.TextChoices):
        ALL = 'all', 'Tous les utilisateurs'
        ADMINS = 'admins', 'Administrateurs seulement'

    mode = models.CharField(
        max_length=10,
        choices=Mode.choices,
        default=Mode.OFF,
        verbose_name='Mode',
    )
    applies_to = models.CharField(
        max_length=10,
        choices=AppliesTo.choices,
        default=AppliesTo.ALL,
        verbose_name='Périmètre',
    )

    class Meta:
        verbose_name = 'Politique réseau'
        verbose_name_plural = 'Politiques réseau'
        constraints = [
            models.UniqueConstraint(
                fields=['company'],
                name='uniq_networkpolicy_par_societe',
            ),
        ]

    def __str__(self):
        return f'NetworkPolicy({self.company_id}, {self.mode})'


class IpAllowRule(TenantModel):
    """Une plage CIDR (ou IP unique) autorisée par une ``NetworkPolicy``."""

    policy = models.ForeignKey(
        NetworkPolicy,
        on_delete=models.CASCADE,
        related_name='rules',
        verbose_name='Politique',
    )
    cidr = models.CharField(
        max_length=64,
        verbose_name='Plage CIDR',
        help_text='Ex. 192.168.1.0/24 ou 41.92.0.10/32.',
    )
    label = models.CharField(
        max_length=120,
        blank=True,
        default='',
        verbose_name='Libellé',
    )

    class Meta:
        verbose_name = 'Règle IP autorisée'
        verbose_name_plural = 'Règles IP autorisées'

    def __str__(self):
        return self.cidr

    def clean(self):
        super().clean()
        try:
            ipaddress.ip_network(self.cidr.strip(), strict=False)
        except (ValueError, AttributeError):
            raise ValidationError(
                {'cidr': 'Plage CIDR invalide (ex. 10.0.0.0/8).'})

    def save(self, *args, **kwargs):
        # Normalise la saisie et garantit la validité (jamais de plage cassée
        # en base, qui rendrait le middleware imprévisible).
        self.cidr = (self.cidr or '').strip()
        self.full_clean(exclude=['company', 'policy'])
        super().save(*args, **kwargs)


class TrustedDevice(TenantModel):
    """NTSEC14 — appareil approuvé (« se souvenir de cet appareil N jours »).

    Sur un appareil de confiance NON expiré et NON révoqué, le second facteur
    MFA est sauté à la connexion — MAIS uniquement si la société l'autorise via
    ``CompanyProfile.allow_device_trust`` (défaut False). Sans opt-in société,
    ce modèle est inerte : la MFA reste toujours exigée.

    ``device_fingerprint`` est un jeton opaque tiré au sort côté serveur au
    moment de l'approbation, posé en cookie httpOnly ``device_trust_id`` ; il
    n'est jamais dérivé d'un secret et ne remplace pas le mot de passe.
    """

    user = models.ForeignKey(
        'authentication.CustomUser',
        on_delete=models.CASCADE,  # on_delete: un appareil de confiance n'existe que pour son utilisateur
        related_name='trusted_devices',
        verbose_name='Utilisateur',
    )
    device_fingerprint = models.CharField(
        max_length=128,
        db_index=True,
        verbose_name='Empreinte appareil',
    )
    approuve_le = models.DateTimeField(verbose_name='Approuvé le')
    expire_le = models.DateTimeField(verbose_name='Expire le')
    approuve_par = models.ForeignKey(
        'authentication.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        verbose_name='Approuvé par',
    )
    revoque_le = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Révoqué le',
    )
    label = models.CharField(
        max_length=200,
        blank=True,
        default='',
        verbose_name='Appareil',
    )

    class Meta:
        verbose_name = 'Appareil de confiance'
        verbose_name_plural = 'Appareils de confiance'
        ordering = ('-approuve_le',)

    def __str__(self):
        return f'TrustedDevice({self.user_id}, {self.device_fingerprint[:8]})'

    @property
    def is_active(self):
        from django.utils import timezone
        return self.revoque_le is None and self.expire_le > timezone.now()

    @classmethod
    def is_trusted(cls, user, fingerprint):
        """Vrai si ``fingerprint`` correspond à un appareil de confiance ACTIF
        (non expiré, non révoqué) de ``user`` dans SA société. Default-deny :
        toute anomalie ⇒ False (la MFA sera exigée)."""
        from django.utils import timezone
        if user is None or not fingerprint:
            return False
        company = getattr(user, 'company', None)
        if company is None:
            return False
        return cls.objects.filter(
            user=user,
            company=company,
            device_fingerprint=fingerprint,
            revoque_le__isnull=True,
            expire_le__gt=timezone.now(),
        ).exists()
