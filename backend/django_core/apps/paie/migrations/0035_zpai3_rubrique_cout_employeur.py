# Generated manually — ZPAI3 flag Rubrique.apparait_cout_employeur : champ
# additif (défaut True = comportement historique inchangé), aucune donnée
# existante touchée.

from django.db import migrations, models


class Migration(migrations.Migration):
    """ZPAI3 — Rubrique.apparait_cout_employeur (additif)."""

    dependencies = [
        ("paie", "0034_yledg7_ecritures_reglement"),
    ]

    operations = [
        migrations.AddField(
            model_name="rubrique",
            name="apparait_cout_employeur",
            field=models.BooleanField(
                default=True,
                verbose_name="Apparaît au coût employeur"),
        ),
    ]
