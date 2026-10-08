"""ASEC8 — caviardage des champs SECRETS dans le journal d'audit.

Le diff automatique (``signals._diff_from_snapshot``) lit le pré-instantané
``values()`` — qui DÉCHIFFRE les ``EncryptedCharField`` — et recopiait donc en
clair dans ``AuditLog.changes`` le secret TOTP, le hash du mot de passe, les
codes de secours… que la restitution « as-of » resservait ensuite. Ici, la
liste déclarée des champs secrets et la fonction unique qui les caviarde : le
CHANGEMENT reste tracé (``{"field": "totp_secret", "old": "***", "new":
"***"}``), jamais la valeur.

Distinct de ``signals._DIFF_NOISE_FIELDS`` (bruit de bookkeeping, exclu du
diff) : un champ secret reste DANS le diff, caviardé.
"""

MASQUE = '***'

#: Noms de champs secrets, quel que soit le modèle.
CHAMPS_SECRETS = frozenset({
    'password',
    'totp_secret',
    'totp_recovery_codes',
})


def _est_chiffre(field):
    """Tout champ chiffré au repos (``core.crypto_fields``) est secret."""
    return any(cls.__name__.startswith('Encrypted')
               for cls in type(field).__mro__)


def champs_secrets_du_modele(model):
    """Noms (``name`` ET ``attname``) des champs secrets de ``model``."""
    noms = set()
    for field in model._meta.concrete_fields:
        if field.name in CHAMPS_SECRETS or field.attname in CHAMPS_SECRETS \
                or _est_chiffre(field):
            noms.add(field.name)
            noms.add(field.attname)
    return noms


def caviarder(model, changes):
    """Copie de ``changes`` (``[{field, old, new}, …]``) où les valeurs des
    champs secrets de ``model`` sont remplacées par ``MASQUE``. ``None`` et
    une liste vide passent tels quels."""
    if not changes:
        return changes
    secrets = champs_secrets_du_modele(model) if model is not None \
        else set(CHAMPS_SECRETS)
    sortie = []
    for change in changes:
        if isinstance(change, dict) and change.get('field') in secrets:
            change = {**change, 'old': MASQUE, 'new': MASQUE}
        sortie.append(change)
    return sortie


def caviarder_valeur(model, field, valeur):
    """``MASQUE`` si ``field`` est un champ secret de ``model``, sinon
    ``valeur`` (restitution « as-of »)."""
    secrets = champs_secrets_du_modele(model) if model is not None \
        else set(CHAMPS_SECRETS)
    return MASQUE if field in secrets else valeur
