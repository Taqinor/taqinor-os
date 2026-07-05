# ZSTK11 — Méthode de réservation du stock (Odoo "Reservation methods") :
# confirmation (défaut, byte-identique) ou manuelle (bouton explicite).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parametres", "0045_yhire9_mode_garde_habilitation"),
    ]

    operations = [
        migrations.AddField(
            model_name="companyprofile",
            name="methode_reservation_stock",
            field=models.CharField(
                choices=[
                    ("confirmation", "À la confirmation"),
                    ("manuelle", "Manuelle"),
                ],
                default="confirmation", max_length=20,
                help_text="Réserver le stock automatiquement à la création "
                          "du chantier (défaut, comportement historique) ou "
                          "manuellement via un bouton explicite."),
        ),
    ]
