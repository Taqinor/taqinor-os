# XSAL16 — Analytics d'engagement par section de la proposition web.
# Additive/reversible: two nullable fields on the existing ShareLink table.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0072_xsal12_livraisonbc'),
    ]

    operations = [
        migrations.AddField(
            model_name='sharelink',
            name='engagement',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='sharelink',
            name='deep_engagement_logged_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
