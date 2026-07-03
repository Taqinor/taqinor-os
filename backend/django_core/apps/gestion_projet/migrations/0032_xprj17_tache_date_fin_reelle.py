from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_projet', '0031_xprj15_pointavancement'),
    ]

    operations = [
        migrations.AddField(
            model_name='tache',
            name='date_fin_reelle',
            field=models.DateField(
                blank=True, null=True, verbose_name='Date de fin réelle'),
        ),
    ]
