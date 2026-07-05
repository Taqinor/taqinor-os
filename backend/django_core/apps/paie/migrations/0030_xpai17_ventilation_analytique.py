# Generated manually — XPAI17 ventilation analytique de la masse salariale
# (clé de répartition fixe par profil, repli quand aucune heure FeuilleTemps
# n'est disponible pour la période).

import django.db.models.deletion
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):
    """XPAI17 — VentilationAnalytiquePaie (clé fixe par profil)."""

    dependencies = [
        ("paie", "0029_xpai24_structure_paie"),
    ]

    operations = [
        migrations.CreateModel(
            name="VentilationAnalytiquePaie",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("centre_cout_id", models.PositiveIntegerField(
                    verbose_name="Centre de coût (ID, compta.CentreCout)")),
                ("pourcentage", models.DecimalField(
                    decimal_places=2, default=Decimal("100"), max_digits=5,
                    verbose_name="Pourcentage")),
                ("actif", models.BooleanField(default=True, verbose_name="Actif")),
                ("date_creation", models.DateTimeField(
                    auto_now_add=True, verbose_name="Créée le")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="paie_ventilations_analytiques",
                    to="authentication.company", verbose_name="Société")),
                ("profil", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="ventilations_analytiques",
                    to="paie.profilpaie", verbose_name="Profil de paie")),
            ],
            options={
                "verbose_name": "Ventilation analytique (clé fixe)",
                "verbose_name_plural": "Ventilations analytiques (clés fixes)",
                "ordering": ["profil", "id"],
            },
        ),
    ]
