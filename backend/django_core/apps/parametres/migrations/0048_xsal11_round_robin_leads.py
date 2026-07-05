# XSAL11 — Balanced round-robin lead assignment toggle (additive, OFF by
# default = behaviour unchanged) + configurable open-lead cap per commercial.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parametres", "0047_zstk11_methode_reservation_stock"),
    ]

    operations = [
        migrations.AddField(
            model_name="companyprofile",
            name="round_robin_leads_actif",
            field=models.BooleanField(
                default=False,
                verbose_name="Affectation round-robin équilibrée des leads",
                help_text="OFF = comportement actuel (round-robin simple ou "
                          "responsable par défaut). ON = plafond de leads "
                          "ouverts par commercial appliqué avant rotation.",
            ),
        ),
        migrations.AddField(
            model_name="companyprofile",
            name="round_robin_plafond_leads_ouverts",
            field=models.PositiveIntegerField(
                default=20,
                verbose_name="Plafond de leads ouverts par commercial",
                help_text="Un commercial au-delà de ce nombre de leads "
                          "OUVERTS (stage non SIGNED/COLD, non perdu) est "
                          "sauté dans la rotation (XSAL11).",
            ),
        ),
    ]
