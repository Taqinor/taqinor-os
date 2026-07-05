# Generated manually — ZPAI12 PeriodePaie.date_alerte_cloture_retard : champ
# additif (NULL par défaut = comportement historique inchangé, aucune
# période existante n'est rétroactivement marquée). Aucune donnée touchée.

from django.db import migrations, models


class Migration(migrations.Migration):
    """ZPAI12 — PeriodePaie.date_alerte_cloture_retard (additif)."""

    dependencies = [
        ("paie", "0040_zpai11_elementvariable_reconduire"),
    ]

    operations = [
        migrations.AddField(
            model_name="periodepaie",
            name="date_alerte_cloture_retard",
            field=models.DateTimeField(
                blank=True, null=True,
                verbose_name="Alerte de clôture en retard envoyée le"),
        ),
    ]
