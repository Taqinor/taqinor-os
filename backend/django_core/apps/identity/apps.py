from django.apps import AppConfig


class IdentityConfig(AppConfig):
    """App de FONDATION identité fédérée (NTSEC).

    Porte la couche identité enterprise : SSO SAML/OIDC par tenant (NTSEC1-4),
    provisioning SCIM 2.0 (NTSEC5-6), JIT depuis les groupes SSO (NTSEC7),
    break-glass (NTSEC22)… Comme les autres apps de fondation (records,
    customfields), elle N'IMPORTE aucune app MÉTIER : elle ne dépend que de
    ``authentication`` / ``roles`` / ``audit`` (apps de fondation, exemptées du
    contrat import-linter). Scope société toujours forcé côté serveur.

    Tout est key-gated OFF par défaut : sans IdP/jeton configuré, le
    comportement d'authentification reste octet-identique à l'existant (login
    local inchangé).
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.identity'
    label = 'identity'
    verbose_name = 'Identité fédérée & SSO'
    module_manifest = {
        'key': 'identity',
        'label': 'Identité & SSO',
        'icone': 'shield-check',
        'depends': [],
        'installable': False,
        'description': 'SSO SAML/OIDC, SCIM 2.0, break-glass, sécurité '
                       'identité enterprise.',
        'categorie': 'Technique',
    }
