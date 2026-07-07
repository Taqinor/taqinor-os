# ZSTK2 - fenetre d'alerte de peremption (jours) pour la tache beat
# stock.expiration_alerts. Additif : defaut 30 = comportement inchange tant
# que la tache n'est pas active (best-effort, jamais bloquant).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parametres", "0047_zstk11_methode_reservation_stock"),
    ]

    operations = [
        migrations.AddField(
            model_name="companyprofile",
            name="jours_alerte_peremption",
            field=models.PositiveIntegerField(
                default=30,
                help_text=(
                    "Fenêtre (jours) au-delà de laquelle un lot proche de "
                    "sa péremption déclenche une alerte automatique "
                    "quotidienne."),
            ),
        ),
    ]
