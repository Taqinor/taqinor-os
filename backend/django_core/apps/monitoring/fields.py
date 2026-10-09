"""ASAV71 — champ JSON chiffré au repos pour les identifiants des connecteurs.

Compose la couche existante ``core.crypto_fields.EncryptedTextField`` (YHARD1 :
Fernet, key-gated par ``FIELD_ENCRYPTION_KEY`` — sans clé configurée, la
colonne garde le JSON en clair, comme tout champ chiffré du dépôt) avec une
sérialisation JSON : l'application manipule un ``dict`` ; la colonne brute ne
contient qu'un jeton ``enc:…`` quand la clé est posée.
"""
import json

from core.crypto_fields import (
    EncryptedTextField, decrypt_value, encrypt_value,
)


class EncryptedJSONField(EncryptedTextField):
    """``dict`` Python ↔ colonne TEXT chiffrée (JSON sérialisé)."""

    def get_prep_value(self, value):
        if value is None:
            return None
        if isinstance(value, str):
            texte = value
        else:
            texte = json.dumps(value)
        return encrypt_value(texte)

    def _vers_objet(self, brut):
        texte = decrypt_value(brut)
        if texte in (None, ''):
            return {}
        try:
            return json.loads(texte)
        except (TypeError, ValueError):
            return {}

    def from_db_value(self, value, expression, connection):
        return self._vers_objet(value)

    def to_python(self, value):
        if isinstance(value, (dict, list)) or value is None:
            return value
        return self._vers_objet(value)

    def value_to_string(self, obj):
        return json.dumps(self.value_from_object(obj))
