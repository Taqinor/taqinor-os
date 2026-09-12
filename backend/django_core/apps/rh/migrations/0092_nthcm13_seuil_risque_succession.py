# NTHCM13 — seuil (Paramètres RH) du croisement criticité × flight-risk.
#
# ADDITIF : un seul champ, défaut 60 — le comportement des sociétés
# existantes est celui du défaut documenté, aucune donnée n'est réécrite.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rh', '0091_nthcm12_poste_cle_succession'),
    ]

    operations = [
        migrations.AddField(
            model_name='reglagerh',
            name='seuil_risque_succession',
            field=models.PositiveSmallIntegerField(
                default=60,
                verbose_name='Seuil de risque succession (0-100)'),
        ),
    ]
