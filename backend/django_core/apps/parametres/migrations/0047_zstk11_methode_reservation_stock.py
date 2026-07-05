# ZSTK11 — Méthode de réservation du stock (Odoo "Reservation methods") :
# confirmation (défaut, byte-identique) ou manuelle (bouton explicite).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parametres", "0046_zsal5_emailtemplate_envoi_devis"),
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
