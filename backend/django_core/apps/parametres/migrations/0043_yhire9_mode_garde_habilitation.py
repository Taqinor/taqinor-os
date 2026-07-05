# YHIRE9 — Garde d'habilitation à l'affectation d'intervention : mode
# configurable (warn/block, défaut warn = quasi byte-identique).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parametres", "0042_yserv1_exiger_acompte"),
    ]

    operations = [
        migrations.AddField(
            model_name="companyprofile",
            name="mode_garde_habilitation",
            field=models.CharField(
                choices=[("warn", "Avertir seulement"), ("block", "Bloquer")],
                default="warn", max_length=10,
                help_text="Comportement quand un technicien affecté n'a pas "
                          "l'habilitation requise pour le type "
                          "d'intervention : avertir (défaut) ou bloquer "
                          "l'affectation."),
        ),
    ]
