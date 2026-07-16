"""YHARD1 — chiffrement au repos des champs sensibles (key-gated, réversible).

Couche de FONDATION (n'importe AUCUNE app métier — contrat import-linter
``core-foundation-is-a-base-layer``). Fournit des champs modèle réutilisables
``EncryptedCharField`` / ``EncryptedTextField`` qui chiffrent/déchiffrent À LA
VOLÉE au passage ORM via ``cryptography.fernet`` (AES-128-CBC + HMAC-SHA256).

Deux garanties non négociables :

1. **Key-gated** — la clé est lue depuis ``settings.FIELD_ENCRYPTION_KEY``
   (elle-même issue de l'env ``FIELD_ENCRYPTION_KEY``). *Sans* clé configurée
   le champ se comporte EXACTEMENT comme le ``CharField`` / ``TextField``
   d'origine : aucune transformation, aucune exception, aucun préfixe posé.
2. **Réversible / rétro-compatible** — le texte chiffré est marqué par un
   préfixe (``enc:``). En lecture, une valeur SANS préfixe est renvoyée telle
   quelle (lignes historiques en clair, ou mode sans clé). On peut donc :
     * activer le chiffrement sur une colonne déjà peuplée (les anciennes
       valeurs restent lisibles jusqu'à ré-écriture) ;
     * retirer la clé (les valeurs chiffrées deviennent illisibles mais rien ne
       casse au niveau ORM — le préfixe est simplement renvoyé) ;
   sans jamais perdre de données ni lever à l'``import``/``migrate``.

Rotation de clés : ``FIELD_ENCRYPTION_KEY`` accepte plusieurs clés Fernet
séparées par des virgules — la PREMIÈRE chiffre, TOUTES déchiffrent
(``MultiFernet``), pour tourner une clé sans ré-écrire toute la table d'un coup.

Le stockage colonne est TOUJOURS ``TextField`` (``get_internal_type`` →
``TextField``) : un jeton Fernet est bien plus long que la valeur claire, un
``VARCHAR`` borné déborderait. ``EncryptedCharField`` conserve néanmoins la
sémantique ``CharField`` (``max_length`` pour la validation/formulaire).

Ne JAMAIS exposer une valeur déchiffrée dans une réponse API au-delà de ce qui
l'était déjà : le chiffrement est transparent côté ORM, il ne change PAS les
sérialiseurs — un champ qui n'était pas exposé ne le devient pas ici.
"""
from __future__ import annotations

from functools import lru_cache

from django.db import models

# Marqueur de texte chiffré : permet à des lignes claires (historiques) et
# chiffrées de cohabiter dans la même colonne pendant une migration en ligne.
CIPHER_PREFIX = 'enc:'


def _read_key():
    """Lit la clé (ou les clés) depuis les settings. Renvoie une liste de
    chaînes non vides (éventuellement vide si non configurée)."""
    # Import local : ``settings`` peut être lu au moment de l'appel, jamais à
    # l'import du module (foundation chargée tôt).
    from django.conf import settings
    raw = getattr(settings, 'FIELD_ENCRYPTION_KEY', None) or ''
    return [k.strip() for k in str(raw).split(',') if k.strip()]


@lru_cache(maxsize=8)
def _build_fernet(keys_tuple):
    """Construit un (Multi)Fernet à partir d'un tuple de clés. Mémoïsé sur le
    tuple de clés pour éviter de reconstruire l'objet à chaque valeur."""
    try:
        from cryptography.fernet import Fernet, MultiFernet
    except Exception:  # pragma: no cover - cryptography absent = dégradation
        return None
    try:
        fernets = [Fernet(k.encode() if isinstance(k, str) else k)
                   for k in keys_tuple]
    except Exception:
        # Clé mal formée : on dégrade en « pas de chiffrement » plutôt que de
        # faire crasher tout l'ORM. La garde de configuration est ailleurs.
        return None
    if not fernets:
        return None
    return MultiFernet(fernets) if len(fernets) > 1 else fernets[0]


def _get_fernet():
    keys = _read_key()
    if not keys:
        return None
    return _build_fernet(tuple(keys))


def encrypt_value(value):
    """Chiffre ``value`` (str) → ``"enc:<token>"``. ``None`` / ``""`` et
    l'absence de clé passent tels quels (byte-identique à l'existant)."""
    if value is None or value == '':
        return value
    fernet = _get_fernet()
    if fernet is None:
        return value  # key-gated : aucun chiffrement sans clé
    if isinstance(value, str) and value.startswith(CIPHER_PREFIX):
        return value  # déjà chiffré (double get_prep_value) — idempotent
    token = fernet.encrypt(str(value).encode('utf-8')).decode('ascii')
    return f'{CIPHER_PREFIX}{token}'


def decrypt_value(value):
    """Déchiffre une valeur marquée ``enc:``. Une valeur sans marqueur (clair
    historique ou mode sans clé) est renvoyée telle quelle. Ne lève jamais :
    un jeton indéchiffrable (clé retirée/tournée hors fenêtre) est renvoyé brut
    plutôt que de casser la lecture de toute la ligne."""
    if not isinstance(value, str) or not value.startswith(CIPHER_PREFIX):
        return value
    fernet = _get_fernet()
    if fernet is None:
        return value
    token = value[len(CIPHER_PREFIX):]
    try:
        return fernet.decrypt(token.encode('ascii')).decode('utf-8')
    except Exception:
        return value


class _EncryptedFieldMixin:
    """Logique commune de chiffrement transparent au passage ORM. À composer
    AVANT le champ Django concret (``CharField``/``TextField``)."""

    def get_internal_type(self):
        # Le jeton chiffré n'a pas de longueur bornée fiable → colonne TEXT.
        return 'TextField'

    def get_prep_value(self, value):
        return encrypt_value(super().get_prep_value(value))

    def from_db_value(self, value, expression, connection):
        return decrypt_value(value)

    def to_python(self, value):
        return super().to_python(decrypt_value(value))


class EncryptedCharField(_EncryptedFieldMixin, models.CharField):
    """``CharField`` chiffré au repos (colonne TEXT). Conserve ``max_length``
    pour la validation/formulaire côté application."""


class EncryptedTextField(_EncryptedFieldMixin, models.TextField):
    """``TextField`` chiffré au repos."""
