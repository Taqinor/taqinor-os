# YLEDG5 — chemin d'exception « paiement rejeté » (chèque impayé / virement
# rejeté). Additif : `statut` défaut « encaisse » → comportement historique
# strictement inchangé pour tout paiement existant.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ventes", "0058_xfac18_revue_statut"),
    ]

    operations = [
        migrations.AddField(
            model_name="paiement",
            name="statut",
            field=models.CharField(
                choices=[("encaisse", "Encaissé"), ("rejete", "Rejeté")],
                default="encaisse", max_length=20),
        ),
        migrations.AddField(
            model_name="paiement",
            name="motif_rejet",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="paiement",
            name="frais_rejet",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=10, null=True,
                help_text=(
                    "Frais bancaires optionnels liés au rejet (ex. frais de "
                    "chèque impayé), informatif.")),
        ),
        migrations.AddField(
            model_name="paiement",
            name="date_rejet",
            field=models.DateField(blank=True, null=True),
        ),
    ]
