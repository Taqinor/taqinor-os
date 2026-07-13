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


class IdentityProvider(TenantModel):
    """Fournisseur d'identité (SSO SAML ou OIDC) rattaché à UNE société (NTSEC1).

    Fondation SSO : ce modèle décrit COMMENT une société fédère l'authentification
    (métadonnées, certificat, mapping d'attributs) sans référencer aucune app
    métier. Il est INERTE par défaut (``actif=False``) : tant qu'aucun IdP actif
    n'existe pour la société, le login local reste EXACTEMENT inchangé.

    Un seul IdP ACTIF par couple (société, protocole) — garanti par une
    contrainte d'unicité partielle. Le câblage runtime des flux SAML/OIDC est
    livré séparément (NTSEC2/NTSEC3) ; ici on pose le modèle + le CRUD admin.
    """

    class Protocol(models.TextChoices):
        SAML = 'saml', 'SAML 2.0'
        OIDC = 'oidc', 'OpenID Connect'

    protocol = models.CharField(
        max_length=8,
        choices=Protocol.choices,
        verbose_name='Protocole',
    )
    nom = models.CharField(max_length=120, verbose_name='Nom')
    actif = models.BooleanField(default=False, verbose_name='Actif')

    # Métadonnées de l'IdP : soit une URL de découverte, soit le XML/JSON inline.
    metadata_url = models.URLField(blank=True, default='', max_length=500)
    metadata_xml = models.TextField(blank=True, default='')
    entity_id = models.CharField(max_length=500, blank=True, default='')
    sso_url = models.URLField(blank=True, default='', max_length=500)
    x509_cert = models.TextField(blank=True, default='')

    # Mapping d'attributs IdP → champs utilisateur (email/nom/prénom/groupes).
    attribute_map = models.JSONField(default=dict, blank=True)

    # Provisioning à la volée : créer le compte au premier login SSO réussi.
    auto_provision = models.BooleanField(default=False)
    # Rôle par défaut appliqué au compte auto-provisionné (string-FK roles —
    # jamais d'import de ``roles.models`` ici, ``core`` reste fondation).
    default_role_id = models.CharField(max_length=64, blank=True, default='')

    # Une fois activé, interdit le login par mot de passe local (NTSEC4).
    enforce_sso = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Fournisseur d'identité"
        verbose_name_plural = "Fournisseurs d'identité"
        constraints = [
            # Au plus UN IdP actif par (société, protocole). Les IdP inactifs
            # ne sont pas contraints (on peut préparer plusieurs configs).
            models.UniqueConstraint(
                fields=['company', 'protocol'],
                condition=models.Q(actif=True),
                name='uniq_idp_actif_par_societe_protocole',
            ),
        ]

    def __str__(self):
        return f'IdentityProvider({self.company_id}, {self.protocol}, {self.nom})'


class ScimToken(TenantModel):
    """Jeton porteur SCIM 2.0 d'une société (NTSEC5).

    Authentifie un IdP/annuaire qui provisionne des comptes via SCIM. Stocke le
    HASH du jeton (jamais le secret en clair), à l'image de ``publicapi.ApiKey``.
    Scopé société : un jeton n'agit QUE sur les comptes de sa propre société.
    """

    label = models.CharField(max_length=120, blank=True, default='')
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    prefix = models.CharField(max_length=20, blank=True, default='')
    actif = models.BooleanField(default=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Jeton SCIM'
        verbose_name_plural = 'Jetons SCIM'
        indexes = [models.Index(fields=['company', 'actif'])]

    def __str__(self):
        return f'ScimToken({self.company_id}, {self.prefix}…)'

    @classmethod
    def issue(cls, *, company, label=''):
        """Crée un jeton et renvoie ``(instance, jeton_en_clair)``.

        Le secret en clair n'est disponible qu'ici — jamais re-stocké.
        Réutilise le hachage de ``publicapi`` (SHA-256), sans le dupliquer.
        """
        from apps.publicapi.models import (
            VISIBLE_PREFIX_LEN, generate_raw_key, hash_key,
        )
        raw = generate_raw_key()
        inst = cls.objects.create(
            company=company, label=label,
            token_hash=hash_key(raw), prefix=raw[:VISIBLE_PREFIX_LEN])
        return inst, raw


class ScimGroupMapping(TenantModel):
    """Correspondance groupe SCIM → rôle interne (NTSEC6).

    Un groupe SCIM (``scim_group_name``) mappe vers UN ``roles.Role`` de la
    société (``role_id``, STRING-FK — jamais d'import de ``roles.models`` ici).
    L'ajout/retrait d'un membre du groupe applique/retire ce rôle sur le compte,
    via ``apps.roles.services``. Scopé société : un mapping n'attribue jamais un
    rôle d'une autre société.
    """

    scim_group_name = models.CharField(max_length=200, verbose_name='Groupe SCIM')
    role_id = models.CharField(max_length=64, verbose_name='Rôle (id)')

    class Meta:
        verbose_name = 'Mapping groupe SCIM'
        verbose_name_plural = 'Mappings groupes SCIM'
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'scim_group_name'],
                name='uniq_scimgroup_par_societe',
            ),
        ]

    def __str__(self):
        return f'ScimGroupMapping({self.company_id}, {self.scim_group_name})'


class BreakGlassGrant(TenantModel):
    """Accès d'urgence temporaire audité (break-glass, NTSEC22).

    Élève un compte au rôle Administrateur pour une durée bornée, EN
    CONTOURNANT ``enforce_sso`` (voir ``selectors.is_break_glass_active``). Le
    rôle antérieur est figé (``role_legacy_avant`` / ``role_id_avant``) pour être
    RESTAURÉ à la révocation (manuelle ou automatique à l'échéance). Scopé
    société ; chaque octroi exige un motif et est journalisé.
    """

    user = models.ForeignKey(
        'authentication.CustomUser', on_delete=models.CASCADE,
        related_name='break_glass_grants')
    motif = models.TextField()
    accorde_par = models.ForeignKey(
        'authentication.CustomUser', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='break_glass_accordes')
    active_jusqu_a = models.DateTimeField()
    revoque_le = models.DateTimeField(null=True, blank=True)
    # Instantané du rôle antérieur, pour restauration à la révocation.
    role_legacy_avant = models.CharField(max_length=32, blank=True, default='')
    role_id_avant = models.CharField(max_length=64, blank=True, default='')

    class Meta:
        verbose_name = "Accès break-glass"
        verbose_name_plural = "Accès break-glass"
        ordering = ['-created_at']
        indexes = [models.Index(fields=['company', 'user', 'revoque_le'])]

    def __str__(self):
        return f'BreakGlass({self.company_id}, user={self.user_id})'

    @property
    def est_actif(self):
        from django.utils import timezone
        return self.revoque_le is None and self.active_jusqu_a > timezone.now()
