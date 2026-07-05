# Generated manually — ZPAI7 SaisieArret.lot_reference : champ additif
# (défaut '' = comportement historique inchangé), + index de recherche par
# (company, lot_reference) pour l'idempotence de l'éclatement en lot.

from django.db import migrations, models


class Migration(migrations.Migration):
    """ZPAI7 — SaisieArret.lot_reference (additif) + index."""

    dependencies = [
        ("paie", "0036_zpai6_cycle_vie_saisie_arret"),
    ]

    operations = [
        migrations.AddField(
            model_name="saisiearret",
            name="lot_reference",
            field=models.CharField(
                blank=True, default="", max_length=64,
                verbose_name="Référence de lot (idempotence)"),
        ),
        migrations.AddIndex(
            model_name="saisiearret",
            index=models.Index(
                fields=["company", "lot_reference"],
                name="paie_saisie_lot_idx"),
        ),
    ]
