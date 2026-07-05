# Generated manually — ZPAI8 Rubrique.arrondi/sens_arrondi : champs additifs
# (défaut 'aucun'/'sup' = comportement historique inchangé pour toute
# rubrique existante). Aucune donnée existante touchée.

from django.db import migrations, models


class Migration(migrations.Migration):
    """ZPAI8 — Rubrique.arrondi/sens_arrondi (additif)."""

    dependencies = [
        ("paie", "0037_zpai7_saisiearret_lot_reference"),
    ]

    operations = [
        migrations.AddField(
            model_name="rubrique",
            name="arrondi",
            field=models.CharField(
                blank=True,
                choices=[
                    ("aucun", "Aucun"),
                    ("demi_journee", "Demi-journée"),
                    ("journee", "Journée"),
                ],
                default="aucun",
                max_length=13,
                verbose_name="Arrondi (jours d'absence)"),
        ),
        migrations.AddField(
            model_name="rubrique",
            name="sens_arrondi",
            field=models.CharField(
                blank=True,
                choices=[("sup", "Arrondi supérieur"), ("inf", "Arrondi inférieur")],
                default="sup",
                max_length=3,
                verbose_name="Sens de l'arrondi"),
        ),
    ]
