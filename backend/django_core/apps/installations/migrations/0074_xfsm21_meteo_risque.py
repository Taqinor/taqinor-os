from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0073_xfsm18_devis_repare'),
    ]

    operations = [
        migrations.AddField(
            model_name='intervention',
            name='meteo_risque',
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='intervention',
            name='meteo_verifie_le',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
