# NTSEC9 — actions sensibles exigeant une MFA récente (additif, inerte).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0060_zstk13_stock_toggles'),
    ]

    operations = [
        migrations.AddField(
            model_name='companyprofile',
            name='step_up_actions',
            field=models.JSONField(
                blank=True, default=list,
                help_text="Clés d'action exigeant une MFA récente (step-up). "
                          "Liste vide = inactif (défaut)."),
        ),
    ]
