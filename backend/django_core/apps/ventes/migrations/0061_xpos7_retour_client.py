# XPOS7 — Retour client avec re-stockage (contre ticket/facture d'origine).
# Additif sur Avoir : `restocke` (défaut False) + `motif_retour` (défaut '')
# — un avoir existant (correction de facturation) reste inchangé.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ventes", "0060_xfac29_dgi_transmission"),
    ]

    operations = [
        migrations.AddField(
            model_name="avoir",
            name="restocke",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="avoir",
            name="motif_retour",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]
