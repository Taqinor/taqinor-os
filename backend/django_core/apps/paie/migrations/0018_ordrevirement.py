# Generated manually — PAIE30 OrdreVirement + LigneVirement (fichier banque).
#
# Additive : ordre de virement des salaires d'une période (regroupe les
# bulletins validés) + ses lignes (un bénéficiaire / un net à virer). Aucun
# comportement existant modifié.

from decimal import Decimal

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """PAIE30 — Ordre de virement + lignes (fichier de virement banque)."""

    dependencies = [
        ("paie", "0017_saisiearret"),
    ]

    operations = [
        migrations.CreateModel(
            name="OrdreVirement",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("libelle", models.CharField(
                    blank=True, default="", max_length=120,
                    verbose_name="Libellé")),
                ("statut", models.CharField(
                    choices=[("brouillon", "Brouillon"), ("emis", "Émis")],
                    default="brouillon", max_length=12,
                    verbose_name="Statut")),
                ("date_execution", models.DateField(
                    blank=True, null=True,
                    verbose_name="Date d'exécution souhaitée")),
                ("rib_emetteur", models.CharField(
                    blank=True, default="", max_length=40,
                    verbose_name="RIB émetteur")),
                ("devise", models.CharField(
                    default="MAD", max_length=3, verbose_name="Devise")),
                ("total", models.DecimalField(
                    decimal_places=2, default=Decimal("0"), max_digits=16,
                    verbose_name="Total à virer")),
                ("nombre_lignes", models.PositiveIntegerField(
                    default=0, verbose_name="Nombre de lignes")),
                ("date_emission", models.DateTimeField(
                    blank=True, null=True, verbose_name="Émis le")),
                ("date_creation", models.DateTimeField(
                    auto_now_add=True, verbose_name="Créé le")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="paie_ordres_virement",
                    to="authentication.company", verbose_name="Société")),
                ("periode", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="ordres_virement", to="paie.periodepaie",
                    verbose_name="Période")),
            ],
            options={
                "verbose_name": "Ordre de virement",
                "verbose_name_plural": "Ordres de virement",
                "ordering": ["-date_creation"],
                "unique_together": {("company", "periode")},
            },
        ),
        migrations.CreateModel(
            name="LigneVirement",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("beneficiaire", models.CharField(
                    max_length=160, verbose_name="Bénéficiaire")),
                ("rib", models.CharField(
                    blank=True, default="", max_length=40,
                    verbose_name="RIB")),
                ("montant", models.DecimalField(
                    decimal_places=2, default=Decimal("0"), max_digits=14,
                    verbose_name="Montant")),
                ("reference", models.CharField(
                    blank=True, default="", max_length=80,
                    verbose_name="Référence")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="paie_lignes_virement",
                    to="authentication.company", verbose_name="Société")),
                ("ordre", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="lignes", to="paie.ordrevirement",
                    verbose_name="Ordre de virement")),
                ("bulletin", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="lignes_virement", to="paie.bulletinpaie",
                    verbose_name="Bulletin")),
            ],
            options={
                "verbose_name": "Ligne de virement",
                "verbose_name_plural": "Lignes de virement",
                "ordering": ["ordre", "beneficiaire", "id"],
            },
        ),
    ]
