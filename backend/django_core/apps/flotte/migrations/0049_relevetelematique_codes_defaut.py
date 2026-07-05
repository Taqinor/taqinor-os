from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flotte', '0048_zonegeographique'),
    ]

    operations = [
        migrations.AddField(
            model_name='relevetelematique',
            name='codes_defaut',
            field=models.JSONField(blank=True, default=list, verbose_name='Codes défaut moteur (DTC)'),
        ),
        migrations.AlterField(
            model_name='referentielflotte',
            name='domaine',
            field=models.CharField(
                choices=[
                    ('type_vehicule', 'Type de véhicule'),
                    ('type_engin', "Type d'engin"),
                    ('energie', 'Énergie'),
                    ('categorie_permis', 'Catégorie de permis'),
                    ('code_dtc', 'Criticité des codes défaut (DTC)'),
                ],
                max_length=30, verbose_name='Domaine'),
        ),
    ]
