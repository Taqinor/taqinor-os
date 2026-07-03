from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0058_xmfg7_serieassemblage'),
    ]

    operations = [
        migrations.AddField(
            model_name='kitcomposant',
            name='taux_perte_pct',
            field=models.DecimalField(decimal_places=2, default=0, help_text='Taux de perte attendu (%) — gonfle le besoin planifié.', max_digits=5),
        ),
    ]
