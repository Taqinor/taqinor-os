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
