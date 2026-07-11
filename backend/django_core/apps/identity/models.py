"""Modèles de la fondation identité fédérée (NTSEC).

``IdentityProvider`` (NTSEC1) — la fondation SSO : une société enregistre un
fournisseur d'identité SAML ou OIDC scopé, activable, avec sa carte
d'attributs et sa politique d'auto-provisioning. Tout est OFF par défaut
(``actif=False``) : tant qu'aucun IdP n'est activé, le login local est
strictement inchangé.
"""
from django.db import models


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
