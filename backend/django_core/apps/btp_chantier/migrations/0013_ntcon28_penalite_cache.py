"""NTCON28 — cache dénormalisé de l'exposition aux pénalités par lot.

Migration ADDITIVE : deux colonnes NULLABLES sur ``Lot``. ``NULL`` signifie
« jamais calculé » — l'API retombe alors sur le calcul synchrone NTCON15,
donc le comportement au déploiement est inchangé tant que le balayage
quotidien n'a pas tourné.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('btp_chantier', '0012_ntcon27_archivage_reserves'),
    ]

    operations = [
        migrations.AddField(
            model_name='lot',
            name='penalite_calculee_cache',
            field=models.JSONField(
                blank=True, null=True,
                verbose_name='Exposition aux pénalités (cache)'),
        ),
        migrations.AddField(
            model_name='lot',
            name='penalite_calculee_le',
            field=models.DateTimeField(
                blank=True, null=True,
                verbose_name='Exposition aux pénalités calculée le'),
        ),
    ]
