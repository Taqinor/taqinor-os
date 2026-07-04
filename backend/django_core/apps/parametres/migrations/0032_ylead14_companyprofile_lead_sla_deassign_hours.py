# YLEAD14 — 2e seuil de recyclage SLA (désassignation) par société. Additive,
# 0 = désactivé (comportement inchangé).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parametres", "0031_xmkt21_companyprofile_seuil_mql"),
    ]

    operations = [
        migrations.AddField(
            model_name="companyprofile",
            name="lead_sla_deassign_hours",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Délai (heures) au-delà duquel un lead SLA-dépassé "
                          "est désassigné (rendu au pool). 0 = jamais "
                          "désassigné (défaut).",
            ),
        ),
    ]
