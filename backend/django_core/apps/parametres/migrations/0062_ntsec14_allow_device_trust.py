# NTSEC14 — opt-in société pour les appareils de confiance (additif, défaut off).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0061_ntsec9_step_up_actions'),
    ]

    operations = [
        migrations.AddField(
            model_name='companyprofile',
            name='allow_device_trust',
            field=models.BooleanField(
                default=False,
                help_text="Autoriser « se souvenir de cet appareil » pour "
                          "sauter la MFA sur un appareil de confiance. Défaut "
                          "False."),
        ),
    ]
