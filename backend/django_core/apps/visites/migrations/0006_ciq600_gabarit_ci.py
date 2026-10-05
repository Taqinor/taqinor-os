from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('visites', '0005_agr412_gabarit_visite'),
    ]

    operations = [
        migrations.AlterField(
            model_name='visiteterrain',
            name='gabarit',
            field=models.CharField(choices=[('toiture', 'Toiture'), ('point_eau', "Relevé du point d'eau"), ('ci', 'Relevé commerce / industrie')], default='toiture', max_length=12, verbose_name='Gabarit de visite'),
        ),
    ]
