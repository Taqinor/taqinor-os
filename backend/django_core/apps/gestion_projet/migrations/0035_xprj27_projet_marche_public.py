from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_projet', '0034_xprj26_projetactivity_cible'),
    ]

    operations = [
        migrations.AddField(
            model_name='projet',
            name='numero_marche',
            field=models.CharField(
                blank=True, default='', max_length=100,
                verbose_name='N° de marché'),
        ),
        migrations.AddField(
            model_name='projet',
            name='maitre_ouvrage',
            field=models.CharField(
                blank=True, default='', max_length=200,
                verbose_name="Maître d'ouvrage"),
        ),
        migrations.AddField(
            model_name='projet',
            name='delai_execution_jours',
            field=models.PositiveIntegerField(
                blank=True, null=True,
                verbose_name="Délai d'exécution (jours)"),
        ),
        migrations.AddField(
            model_name='projet',
            name='taux_penalite_retard',
            field=models.DecimalField(
                blank=True, decimal_places=3, max_digits=6, null=True,
                verbose_name='Taux de pénalité de retard (‰/jour)'),
        ),
        migrations.AddField(
            model_name='projet',
            name='plafond_penalite_pct',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=5, null=True,
                verbose_name='Plafond de pénalité (%)'),
        ),
        migrations.AddField(
            model_name='projet',
            name='montant_marche',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=14, null=True,
                verbose_name='Montant du marché'),
        ),
        migrations.AddField(
            model_name='projet',
            name='contrat_id',
            field=models.PositiveIntegerField(
                blank=True, null=True,
                verbose_name='ID du contrat (cautions)'),
        ),
    ]
