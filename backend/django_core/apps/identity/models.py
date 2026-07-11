"""Modèles de la fondation identité fédérée (NTSEC).

``IdentityProvider`` (NTSEC1) — la fondation SSO : une société enregistre un
fournisseur d'identité SAML ou OIDC scopé, activable, avec sa carte
d'attributs et sa politique d'auto-provisioning. Tout est OFF par défaut
(``actif=False``) : tant qu'aucun IdP n'est activé, le login local est
strictement inchangé.
"""
import hashlib
import hmac
import secrets

from django.conf import settings
from django.db import models


SCIM_TOKEN_PREFIX = 'scim_'


def hash_scim_token(raw):
    """Empreinte HMAC-SHA256 « poivrée » d'un jeton SCIM (indexable, O(1)).

    Même patron que ``publicapi.hash_key`` : un jeton SCIM est un secret à haute
    entropie, on stocke/compare une empreinte déterministe poivrée par la
    SECRET_KEY du serveur (une fuite de table reste inexploitable hors-ligne)."""
    return hmac.new(
        settings.SECRET_KEY.encode('utf-8'),
        raw.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()


def generate_scim_token():
    return SCIM_TOKEN_PREFIX + secrets.token_urlsafe(32)


class IdentityProvider(models.Model):
    """Fournisseur d'identité (IdP) SSO d'une société — SAML 2.0 ou OIDC.

    Scopé société (FK obligatoire, forcé côté serveur). Un seul IdP ACTIF par
    couple (société, protocole) : la contrainte partielle empêche deux SAML (ou
    deux OIDC) actifs simultanés pour une même société. Les IdP inactifs
    (brouillons) peuvent coexister sans limite.
    """

    PROTOCOL_SAML = 'saml'
    PROTOCOL_OIDC = 'oidc'
    PROTOCOL_CHOICES = [
        (PROTOCOL_SAML, 'SAML 2.0'),
        (PROTOCOL_OIDC, 'OpenID Connect'),
    ]

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='identity_providers',
    )
    protocol = models.CharField(
        max_length=8, choices=PROTOCOL_CHOICES,
        help_text='Protocole de fédération (SAML 2.0 ou OIDC).')
    nom = models.CharField(
        max_length=120,
        help_text="Libellé lisible de l'IdP (ex. « Azure AD », « Okta »).")
    # OFF par défaut : un IdP tant qu'il n'est pas activé ne change RIEN au
    # comportement de connexion existant (login local intact).
    actif = models.BooleanField(
        default=False,
        help_text="Active l'IdP pour la connexion SSO. OFF par défaut = login "
                  'local inchangé.')

    # ── Découverte / métadonnées ────────────────────────────────────────────
    # SAML : URL de métadonnées de l'IdP OU XML collé. OIDC : URL
    # `.well-known/openid-configuration` (découverte automatique).
    metadata_url = models.URLField(
        max_length=500, blank=True, default='',
        help_text='URL de métadonnées SAML ou de découverte OIDC '
                  '(.well-known/openid-configuration).')
    metadata_xml = models.TextField(
        blank=True, default='',
        help_text='Métadonnées SAML collées (alternative à metadata_url).')

    # ── Paramètres SAML / OIDC bruts (renseignés si pas de découverte) ───────
    entity_id = models.CharField(
        max_length=255, blank=True, default='',
        help_text="EntityID / Issuer de l'IdP (SAML) ou issuer OIDC.")
    sso_url = models.URLField(
        max_length=500, blank=True, default='',
        help_text="URL de connexion de l'IdP (SAML SSO / OIDC "
                  'authorization_endpoint).')
    x509_cert = models.TextField(
        blank=True, default='',
        help_text="Certificat X.509 (PEM) de l'IdP servant à valider la "
                  'signature des assertions SAML / id_token.')

    # ── OIDC — identifiants client (par tenant) ─────────────────────────────
    client_id = models.CharField(
        max_length=255, blank=True, default='',
        help_text='client_id OIDC enregistré auprès de l\'IdP.')
    client_secret = models.CharField(
        max_length=255, blank=True, default='',
        help_text='client_secret OIDC (par tenant). Vide pour un flow public '
                  'PKCE seul.')

    # ── Carte d'attributs / claims → champs utilisateur ─────────────────────
    # JSON : {"email": <attr>, "nom": <attr>, "prenom": <attr>,
    #         "groupes": <attr>}. Sert à mapper l'assertion/le token vers le
    # CustomUser (NTSEC2/3) et à extraire les groupes pour le JIT (NTSEC7).
    attribute_map = models.JSONField(
        default=dict, blank=True,
        help_text='Correspondance attribut IdP → champ utilisateur '
                  '(email/nom/prenom/groupes).')

    # Créer automatiquement l'utilisateur absent lors d'une connexion SSO
    # réussie (NTSEC2/3/7). OFF par défaut : sans opt-in, seuls les comptes
    # existants peuvent se connecter par SSO.
    auto_provision = models.BooleanField(
        default=False,
        help_text="Crée automatiquement l'utilisateur absent à la première "
                  'connexion SSO (auto-provisioning).')
    # Rôle par défaut appliqué à un utilisateur auto-provisionné (ou en repli
    # d'un groupe SSO non mappé, NTSEC7). Référence par STRING-FK vers
    # roles.Role — aucune importation des modèles roles ici. SET_NULL : retirer
    # le rôle détache simplement le défaut.
    default_role = models.ForeignKey(
        'roles.Role',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+',
        help_text='Rôle attribué par défaut à un compte SSO auto-provisionné.')

    # Interdire le login local (mot de passe) pour les membres de la société
    # une fois l'IdP actif (NTSEC4). OFF par défaut : le login local reste
    # autorisé tant que la société ne l'impose pas.
    enforce_sso = models.BooleanField(
        default=False,
        help_text='Interdit le login local (mot de passe) une fois activé — '
                  'les comptes doivent passer par le SSO (NTSEC4).')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Fournisseur d'identité (SSO)"
        verbose_name_plural = "Fournisseurs d'identité (SSO)"
        ordering = ['company', 'protocol', 'nom']
        constraints = [
            # Un seul IdP ACTIF par (société, protocole). Les IdP inactifs
            # (brouillons) ne sont pas contraints.
            models.UniqueConstraint(
                fields=['company', 'protocol'],
                condition=models.Q(actif=True),
                name='identity_one_active_idp_per_company_protocol',
            ),
        ]

    def __str__(self):
        return f'{self.company_id} — {self.get_protocol_display()} · {self.nom}'


class ConsumedAssertion(models.Model):
    """Cache anti-rejeu des assertions SAML consommées (NTSEC2).

    Chaque ``assertion_id`` d'une réponse SAML validée est enregistré ici ; une
    réponse rejouée (même id) est refusée. ``expire_le`` = borne de validité de
    l'assertion (``NotOnOrAfter``) : un nettoyage best-effort purge les entrées
    échues. Scopé société pour ne jamais fuiter entre tenants.
    """

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='consumed_assertions',
    )
    assertion_id = models.CharField(max_length=255, db_index=True)
    consumed_at = models.DateTimeField(auto_now_add=True)
    expire_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Assertion SAML consommée'
        verbose_name_plural = 'Assertions SAML consommées'
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'assertion_id'],
                name='identity_unique_assertion_per_company',
            ),
        ]

    def __str__(self):
        return f'{self.company_id} — {self.assertion_id}'


class OidcAuthState(models.Model):
    """État transitoire d'un flux OIDC Authorization Code + PKCE (NTSEC3).

    Créé au ``login/`` (redirection vers l'IdP) et consommé une seule fois au
    ``callback/`` : porte le ``state`` (anti-CSRF), le ``nonce`` (anti-rejeu de
    l'id_token) et le ``code_verifier`` PKCE. Scopé société, à usage unique
    (``used=True`` après consommation), avec une fenêtre de validité courte.
    """

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='oidc_states',
    )
    state = models.CharField(max_length=128, unique=True, db_index=True)
    nonce = models.CharField(max_length=128)
    code_verifier = models.CharField(max_length=128)
    used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'État OIDC (PKCE)'
        verbose_name_plural = 'États OIDC (PKCE)'

    def __str__(self):
        return f'{self.company_id} — {self.state[:12]}…'


class ScimToken(models.Model):
    """Jeton porteur dédié au provisioning SCIM 2.0 d'une société (NTSEC5).

    Authentifie l'IdP appelant le service SCIM. Seul un HASH est stocké ; le
    secret en clair n'est montré qu'une fois, à l'émission. Scopé société,
    révocable (``actif``). ``last_rotated_at``/``rotation_period_days`` (NTSEC29)
    sont posés additifs, défaut inerte.
    """

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='scim_tokens',
    )
    label = models.CharField(max_length=120, blank=True, default='')
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    prefix = models.CharField(max_length=20, blank=True, default='')
    actif = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='scim_tokens_crees',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    # NTSEC29 — registre de rotation (réutilise YHARD5). Défaut inerte.
    last_rotated_at = models.DateTimeField(null=True, blank=True)
    rotation_period_days = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Jeton SCIM'
        verbose_name_plural = 'Jetons SCIM'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.company_id} — SCIM {self.prefix}…'

    @classmethod
    def issue(cls, *, company, label='', created_by=None):
        """Crée un jeton et renvoie (instance, jeton_en_clair)."""
        raw = generate_scim_token()
        instance = cls.objects.create(
            company=company,
            label=label,
            token_hash=hash_scim_token(raw),
            prefix=raw[:12],
            created_by=created_by,
        )
        return instance, raw


class ScimGroupMapping(models.Model):
    """Mappe un groupe SCIM/SSO vers un rôle de la société (NTSEC6/NTSEC7).

    L'ajout/retrait d'un membre d'un groupe SCIM applique/retire le rôle
    correspondant ; réutilisé par le JIT SSO (NTSEC7). Scopé société. Le rôle
    est référencé par STRING-FK (``roles.Role``) — aucun import des modèles
    roles ici.
    """

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='scim_group_mappings',
    )
    scim_group_name = models.CharField(max_length=255)
    role = models.ForeignKey(
        'roles.Role',
        on_delete=models.CASCADE,
        related_name='+',
    )

    class Meta:
        verbose_name = 'Mapping groupe SCIM → rôle'
        verbose_name_plural = 'Mappings groupe SCIM → rôle'
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'scim_group_name'],
                name='identity_unique_scim_group_per_company',
            ),
        ]

    def __str__(self):
        return f'{self.company_id} — {self.scim_group_name} → {self.role_id}'
