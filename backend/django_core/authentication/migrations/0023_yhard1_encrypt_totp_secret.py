"""YHARD1 — chiffrement au repos du secret TOTP.

``CustomUser.totp_secret`` passe de ``CharField`` à ``EncryptedCharField``
(couche fondation ``core.crypto_fields``). La colonne devient TEXT (un jeton
Fernet est plus long qu'un VARCHAR borné). ADDITIF et RÉVERSIBLE :

* sans ``FIELD_ENCRYPTION_KEY`` configurée le champ se comporte exactement
  comme l'ancien ``CharField`` (aucun chiffrement, aucune valeur touchée) ;
* les lignes historiques en clair restent lisibles (le déchiffrement ignore
  les valeurs sans préfixe ``enc:``) — pas de RunPython de transformation ;
* le rollback rétablit un ``CharField`` (Django dérive l'état inverse).
"""
import core.crypto_fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0022_usersession_device_fingerprint'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customuser',
            name='totp_secret',
            field=core.crypto_fields.EncryptedCharField(
                blank=True, max_length=64, null=True),
        ),
    ]
