# PUB85 — Dimension région optionnelle sur FactEntry : un fait peut porter une
# surcharge régionale VÉRIFIÉE (irradiation/tarif local) en plus de sa valeur
# nationale. L'unicité passe de (table, cle) à (table, cle, region).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('adsengine', '0044_pub70_competitor_intel'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='factentry',
            name='uniq_adseng_factentry_table_cle',
        ),
        migrations.AddField(
            model_name='factentry',
            name='region',
            field=models.CharField(blank=True, default='', max_length=60, verbose_name='Région / ville'),
        ),
        migrations.AddConstraint(
            model_name='factentry',
            constraint=models.UniqueConstraint(fields=['table', 'cle', 'region'], name='uniq_adseng_factentry_table_cle_region'),
        ),
    ]
