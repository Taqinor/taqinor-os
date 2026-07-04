from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flotte', '0052_rappelconstructeur'),
    ]

    operations = [
        migrations.AddField(
            model_name='affectationconducteur',
            name='usage_prive',
            field=models.BooleanField(
                default=False, verbose_name='Usage privé (avantage en nature)'),
        ),
        migrations.AddField(
            model_name='affectationconducteur',
            name='valeur_avantage_mensuelle',
            field=models.DecimalField(
                decimal_places=2, default=0, max_digits=10,
                verbose_name="Valeur de l'avantage en nature (MAD/mois)"),
        ),
    ]
