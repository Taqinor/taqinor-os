"""Câblage SAML 2.0 par tenant (NTSEC2) via ``python3-saml`` (OSS).

La dépendance ``python3-saml`` (paquet ``onelogin``) est importée
PARESSEUSEMENT et de façon GARDÉE : sans le wheel installé, ``saml_available()``
renvoie False et les endpoints SAML dégradent proprement en 501 (« SSO SAML non
disponible »), sans jamais casser l'import de l'app ni le login local. C'est le
même patron défensif que statsmodels / pyHanko dans ce repo.
"""
import logging

logger = logging.getLogger(__name__)


def saml_available():
    """True si ``python3-saml`` (onelogin) est installé."""
    try:
        import onelogin.saml2.auth  # noqa: F401
        return True
    except Exception:  # noqa: BLE001 — absence de wheel = dégradation propre
        return False


def build_saml_settings(idp, request):
    """Construit le dict de configuration ``python3-saml`` pour un IdP + SP.

    Le SP (Service Provider = notre ERP) est dérivé de l'URL courante par
    société : entityId = URL des métadonnées, ACS = endpoint ACS de la société.
    L'IdP (entityId/SSO URL/certificat) vient du modèle ``IdentityProvider``.
    """
    base = _sp_base_url(request, idp.company)
    return {
        'strict': True,
        'debug': False,
        'sp': {
            'entityId': f'{base}/metadata/',
            'assertionConsumerService': {
                'url': f'{base}/acs/',
                'binding': 'urn:oasis:names:tc:SAML:2.0:bindings:'
                           'HTTP-POST',
            },
            'singleLogoutService': {
                'url': f'{base}/sls/',
                'binding': 'urn:oasis:names:tc:SAML:2.0:bindings:'
                           'HTTP-Redirect',
            },
            'NameIDFormat': 'urn:oasis:names:tc:SAML:1.1:nameid-format:'
                            'emailAddress',
            'x509cert': '',
            'privateKey': '',
        },
        'idp': {
            'entityId': idp.entity_id,
            'singleSignOnService': {
                'url': idp.sso_url,
                'binding': 'urn:oasis:names:tc:SAML:2.0:bindings:'
                           'HTTP-Redirect',
            },
            'x509cert': idp.x509_cert,
        },
    }


def _sp_base_url(request, company):
    """URL de base des endpoints SAML de la société (sans slash final)."""
    scheme = 'https' if request.is_secure() else 'http'
    host = request.get_host()
    return f'{scheme}://{host}/api/django/identity/saml/{company.slug}'


def build_request_dict(request):
    """Adapte une requête Django au format attendu par ``python3-saml``."""
    return {
        'https': 'on' if request.is_secure() else 'off',
        'http_host': request.get_host(),
        'script_name': request.path,
        'get_data': request.GET.copy(),
        'post_data': request.POST.copy(),
    }


def build_auth(idp, request):
    """Instancie ``OneLogin_Saml2_Auth`` pour un IdP donné (lib requise)."""
    from onelogin.saml2.auth import OneLogin_Saml2_Auth
    return OneLogin_Saml2_Auth(
        build_request_dict(request), build_saml_settings(idp, request))
