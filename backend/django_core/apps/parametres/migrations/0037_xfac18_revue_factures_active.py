# XFAC18 — Workflow de revue facture (ségrégation des tâches, style Odoo 19).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parametres", "0036_xfac13_tolerance_ecart_reglement"),
    ]

    operations = [
        migrations.AddField(
            model_name="companyprofile",
            name="revue_factures_active",
            field=models.BooleanField(
                default=False,
                help_text="Active le contrôle 4-yeux à l'émission des "
                          "factures (désactivé par défaut)."),
        ),
    ]
