"""ADOC64 — dégradation OTP explicite d'un destinataire de signature.

Additive et revertable : un booléen `otp_degrade` (défaut False) sur
`SignataireDemande`, posé par `envoyer_code_otp_signataire` quand la passerelle
SMS/email est absente.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ged', '0050_acl_client_idx_concurrent'),
    ]

    operations = [
        migrations.AddField(
            model_name='signatairedemande',
            name='otp_degrade',
            field=models.BooleanField(
                default=False,
                verbose_name='authentification extra dégradée'),
        ),
    ]
