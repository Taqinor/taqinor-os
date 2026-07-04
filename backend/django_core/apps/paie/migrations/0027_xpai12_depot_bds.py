# Generated manually — XPAI12 BDS complémentaire/rectificative + trace dépôts.
#
# Additif : nouveau modèle DepotBDS (company-scoped) traçant les dépôts BDS
# principaux et complémentaires (self-FK depot_principal, delta uniquement).
# Aucun champ existant modifié.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """XPAI12 — BDS complémentaire/rectificative + format DAMANCOM strict."""

    dependencies = [
        ("paie", "0026_xpai9_modes_paiement_rejets"),
    ]

    operations = [
        migrations.CreateModel(
            name="DepotBDS",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("type_depot", models.CharField(
                    choices=[
                        ("principal", "Principal"),
                        ("complementaire", "Complémentaire"),
                    ],
                    default="principal", max_length=14,
                    verbose_name="Type de dépôt")),
                ("profils_couverts", models.JSONField(
                    blank=True, default=list,
                    verbose_name="Profils couverts")),
                ("date_depot", models.DateTimeField(
                    auto_now_add=True, verbose_name="Déposé le")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="paie_depots_bds",
                    to="authentication.company", verbose_name="Société")),
                ("depot_principal", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="complements", to="paie.depotbds",
                    verbose_name="Dépôt principal référencé")),
                ("periode", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="depots_bds", to="paie.periodepaie",
                    verbose_name="Période")),
            ],
            options={
                "verbose_name": "Dépôt BDS",
                "verbose_name_plural": "Dépôts BDS",
                "ordering": ["-date_depot"],
            },
        ),
    ]
