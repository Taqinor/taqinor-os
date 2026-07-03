# XFAC7 — rappel de courtoisie pré-échéance (J-N avant échéance).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parametres", "0030_qg9_variante_pct"),
    ]

    operations = [
        migrations.AddField(
            model_name="companyprofile",
            name="rappel_pre_echeance_jours",
            field=models.PositiveIntegerField(
                default=5,
                help_text="Jours avant échéance pour le rappel de "
                          "courtoisie (0 = désactivé).",
            ),
        ),
    ]
