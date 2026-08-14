# NTMFG16 — Ordre de préparation-échantillon / prototype (première pièce
# bonne) : flag additif, exclu des calculs agrégés de production normale.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mrp', '0011_ntmfg15_ordre_modification'),
    ]

    operations = [
        migrations.AddField(
            model_name='ordrefabrication',
            name='est_prototype',
            field=models.BooleanField(
                default=False, verbose_name='Prototype (hors production normale)'),
        ),
    ]
