# Revue sécurité du lien public (24/10/2026, point C) — sceau v3 reproductible :
# les chiffres de l'étude C&I lus à l'acceptation sont stockés sur la
# signature. Additif (nullable), réversible.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0139_lien_public_b2b'),
    ]

    operations = [
        migrations.AddField(
            model_name='devissignature',
            name='figures_scellees',
            field=models.JSONField(blank=True, null=True, verbose_name="Chiffres de l'étude C&I scellés à la signature"),
        ),
    ]
