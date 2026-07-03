# Generated manually — XPAI14 indemnités journalières CNSS (maladie/maternité).
#
# Additif : ElementVariable.categorie_absence (aucune/maladie/maternite) —
# un arrêt CNSS neutralise le salaire + cotisations sur les jours indemnisés
# (via le mécanisme existant d'absence non rémunérée) et déclenche
# l'attestation de salaire CNSS. Aucun champ existant modifié.

from django.db import migrations, models


class Migration(migrations.Migration):
    """XPAI14 — Indemnités journalières CNSS (maladie/maternité)."""

    dependencies = [
        ("paie", "0027_xpai12_depot_bds"),
    ]

    operations = [
        migrations.AddField(
            model_name="elementvariable",
            name="categorie_absence",
            field=models.CharField(
                blank=True,
                choices=[
                    ("aucune", "Absence ordinaire"),
                    ("maladie", "Arrêt CNSS — maladie"),
                    ("maternite", "Arrêt CNSS — maternité"),
                ],
                default="aucune", max_length=10,
                verbose_name="Catégorie d'absence"),
        ),
    ]
