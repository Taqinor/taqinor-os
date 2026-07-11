"""Câblage WebAuthn / Passkeys (NTSEC8) via la lib OSS ``webauthn``.

La dépendance ``webauthn`` est importée PARESSEUSEMENT et GARDÉE : sans le wheel
installé, ``webauthn_available()`` renvoie False et les endpoints passkey
dégradent proprement en 501, sans jamais casser l'import de l'app ni le login
local (le passkey est strictement OPT-IN).
"""
import logging

logger = logging.getLogger(__name__)


def webauthn_available():
    """True si la lib ``webauthn`` est installée."""
    try:
        import webauthn  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def rp_id(request):
    """Relying Party ID = domaine de l'ERP (host sans port), ou override env."""
    from django.conf import settings
    override = getattr(settings, 'WEBAUTHN_RP_ID', '') or ''
    if override:
        return override
    host = request.get_host()
    return host.split(':')[0]


def rp_name():
    from django.conf import settings
    return getattr(settings, 'WEBAUTHN_RP_NAME', 'TAQINOR OS')


def origin(request):
    """Origine attendue (scheme://host[:port]) pour la vérification."""
    scheme = 'https' if request.is_secure() else 'http'
    return f'{scheme}://{request.get_host()}'


def sign_count_regressed(current, new):
    """True si ``new`` trahit un CLONE de l'authentificateur (anti-clone NTSEC8).

    Le compteur de signatures d'un authentificateur WebAuthn est monotone
    croissant : à chaque assertion il augmente. Un compteur qui n'augmente PAS
    alors qu'il était déjà > 0 signale qu'une COPIE de la clé a été utilisée
    (deux appareils partageant le même secret dérivent). On tolère le cas
    ``0/0`` (authentificateurs sans compteur — passkeys de plateforme).

    Fonction PURE, testable sans la lib ``webauthn`` — c'est le cœur de sécurité
    de la vérification d'assertion.
    """
    current = current or 0
    new = new or 0
    if current == 0 and new == 0:
        return False
    return new <= current
