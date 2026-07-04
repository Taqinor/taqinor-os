from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flotte', '0050_garage_ice_couvehicule_fournisseur_ref'),
    ]

    operations = [
        migrations.AddField(
            model_name='conducteur',
            name='carte_conducteur_pro_numero',
            field=models.CharField(
                blank=True, max_length=50,
                verbose_name='N° carte de conducteur professionnel'),
        ),
        migrations.AddField(
            model_name='conducteur',
            name='carte_conducteur_pro_expiration',
            field=models.DateField(
                blank=True, null=True,
                verbose_name='Expiration carte de conducteur professionnel'),
        ),
        migrations.AddField(
            model_name='conducteur',
            name='formation_continue_narsa_date',
            field=models.DateField(
                blank=True, null=True,
                verbose_name='Date de formation continue NARSA'),
        ),
        migrations.AddField(
            model_name='conducteur',
            name='formation_continue_narsa_validite',
            field=models.DateField(
                blank=True, null=True,
                verbose_name='Validité de la formation continue NARSA'),
        ),
        migrations.AlterField(
            model_name='echeancereglementaire',
            name='type_echeance',
            field=models.CharField(
                choices=[
                    ('visite_technique', 'Visite technique'),
                    ('assurance', 'Assurance'),
                    ('vignette', 'Vignette / TSAV'),
                    ('carte_grise', 'Carte grise'),
                    ('taxe_essieu', "Taxe à l'essieu"),
                    ('chronotachygraphe', 'Calibration chronotachygraphe'),
                    ('autre', 'Autre'),
                ],
                default='visite_technique', max_length=20,
                verbose_name="Type d'échéance"),
        ),
    ]
