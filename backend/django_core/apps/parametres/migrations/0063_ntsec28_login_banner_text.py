# NTSEC28 — bannière de connexion configurable (additif, vide par défaut).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0062_ntsec14_allow_device_trust'),
    ]

    operations = [
        migrations.AddField(
            model_name='companyprofile',
            name='login_banner_text',
            field=models.TextField(
                blank=True, default='',
                help_text="Mention légale affichée avant authentification "
                          "(accès autorisé uniquement…). Vide = aucun bandeau "
                          "(défaut)."),
        ),
    ]
