# Generated manually — PAIE27 CumulAnnuel (brut/net imposable/IR/CNSS/congés).
#
# Additive : nouveau modèle de cumul annuel par employé, recalculé depuis les
# bulletins validés de l'année. Aucun comportement existant modifié.

from decimal import Decimal

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """PAIE27 — Cumul annuel de paie par employé (totaux d'une année civile)."""

    dependencies = [
        ("paie", "0014_absence_remuneree"),
    ]

    operations = [
        migrations.CreateModel(
            name="CumulAnnuel",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("annee", models.PositiveIntegerField(verbose_name="Année")),
                ("brut", models.DecimalField(
                    decimal_places=2, default=Decimal("0"), max_digits=16,
                    verbose_name="Cumul brut")),
                ("brut_imposable", models.DecimalField(
                    decimal_places=2, default=Decimal("0"), max_digits=16,
                    verbose_name="Cumul brut imposable")),
                ("net_imposable", models.DecimalField(
                    decimal_places=2, default=Decimal("0"), max_digits=16,
                    verbose_name="Cumul net imposable")),
                ("ir", models.DecimalField(
                    decimal_places=2, default=Decimal("0"), max_digits=16,
                    verbose_name="Cumul IR")),
                ("cnss_salariale", models.DecimalField(
                    decimal_places=2, default=Decimal("0"), max_digits=16,
                    verbose_name="Cumul CNSS salariale")),
                ("amo_salariale", models.DecimalField(
                    decimal_places=2, default=Decimal("0"), max_digits=16,
                    verbose_name="Cumul AMO salariale")),
                ("cimr_salariale", models.DecimalField(
                    decimal_places=2, default=Decimal("0"), max_digits=16,
                    verbose_name="Cumul CIMR salariale")),
                ("frais_professionnels", models.DecimalField(
                    decimal_places=2, default=Decimal("0"), max_digits=16,
                    verbose_name="Cumul frais professionnels")),
                ("net_a_payer", models.DecimalField(
                    decimal_places=2, default=Decimal("0"), max_digits=16,
                    verbose_name="Cumul net à payer")),
                ("charges_patronales", models.DecimalField(
                    decimal_places=2, default=Decimal("0"), max_digits=16,
                    verbose_name="Cumul charges patronales")),
                ("provision_conges", models.DecimalField(
                    decimal_places=2, default=Decimal("0"), max_digits=16,
                    verbose_name="Cumul provision congés payés")),
                ("conges_acquis", models.DecimalField(
                    decimal_places=2, default=Decimal("0"), max_digits=8,
                    verbose_name="Congés acquis (jours)")),
                ("conges_pris", models.DecimalField(
                    decimal_places=2, default=Decimal("0"), max_digits=8,
                    verbose_name="Congés pris (jours)")),
                ("nombre_bulletins", models.PositiveIntegerField(
                    default=0, verbose_name="Nombre de bulletins cumulés")),
                ("date_calcul", models.DateTimeField(
                    blank=True, null=True, verbose_name="Recalculé le")),
                ("date_creation", models.DateTimeField(
                    auto_now_add=True, verbose_name="Créé le")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="paie_cumuls_annuels",
                    to="authentication.company", verbose_name="Société")),
                ("profil", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="cumuls_annuels", to="paie.profilpaie",
                    verbose_name="Profil de paie")),
            ],
            options={
                "verbose_name": "Cumul annuel",
                "verbose_name_plural": "Cumuls annuels",
                "ordering": ["-annee", "profil"],
                "unique_together": {("company", "profil", "annee")},
            },
        ),
    ]
