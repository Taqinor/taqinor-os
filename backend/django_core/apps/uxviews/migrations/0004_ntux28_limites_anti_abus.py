# NTUX28 — limites anti-abus configurables sur UxParametres.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('uxviews', '0003_uxparametres'),
    ]

    operations = [
        migrations.AddField(
            model_name='uxparametres',
            name='max_vues_par_utilisateur',
            field=models.PositiveIntegerField(
                default=50, verbose_name='Nombre maximum de vues personnelles par utilisateur'),
        ),
        migrations.AddField(
            model_name='uxparametres',
            name='max_favoris_par_utilisateur',
            field=models.PositiveIntegerField(
                default=30, verbose_name='Nombre maximum de favoris par utilisateur'),
        ),
    ]
