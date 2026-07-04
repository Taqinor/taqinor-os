from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_projet', '0038_zprj7_evaluationprojet'),
    ]

    operations = [
        migrations.AddField(
            model_name='projet',
            name='politique_facturation',
            field=models.CharField(
                choices=[
                    ('forfait', 'Forfait'),
                    ('jalons', "Jalons (facturation à l'avancement)"),
                    ('regie', 'Régie (temps & matériel)'),
                    ('situations', 'Situations de travaux (BTP)'),
                ],
                default='forfait', max_length=12,
                verbose_name='Politique de facturation'),
        ),
    ]
