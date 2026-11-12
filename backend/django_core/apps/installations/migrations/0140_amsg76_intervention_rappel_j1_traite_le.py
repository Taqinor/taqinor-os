# AMSG76 — marqueur « rappel J-1 traité » : un balayage ``rappel_rdv_j1``
# rejoué (worker tué, acks tardifs) ne renvoie pas le rappel. Additif, nullable.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0139_ntplt33_installation_fts_null'),
    ]

    operations = [
        migrations.AddField(
            model_name='intervention',
            name='rappel_j1_traite_le',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
