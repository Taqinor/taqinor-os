# Generated manually — PAIE29 Saisie-arrêt / cession sur salaire.
#
# Additive : nouveau modèle ``SaisieArret`` (saisie judiciaire ou cession
# volontaire) retenu sur le salaire dans la limite de la quotité saisissable.
# Aucun comportement existant modifié.

from decimal import Decimal

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """PAIE29 — Saisie-arrêt / cession sur salaire (quotité saisissable)."""

    dependencies = [
        ("paie", "0016_avancesalarie"),
    ]

    operations = [
        migrations.CreateModel(
            name="SaisieArret",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("type", models.CharField(
                    choices=[("saisie", "Saisie-arrêt (judiciaire)"),
                             ("cession", "Cession volontaire")],
                    default="saisie", max_length=10, verbose_name="Type")),
                ("creancier", models.CharField(
                    blank=True, default="", max_length=160,
                    verbose_name="Créancier")),
                ("reference", models.CharField(
                    blank=True, default="", max_length=80,
                    verbose_name="Référence (jugement/acte)")),
                ("montant_total", models.DecimalField(
                    decimal_places=2, default=Decimal("0"), max_digits=14,
                    verbose_name="Montant total à recouvrer")),
                ("montant_echeance", models.DecimalField(
                    blank=True, decimal_places=2, max_digits=14, null=True,
                    verbose_name="Échéance mensuelle souhaitée")),
                ("montant_retenu", models.DecimalField(
                    decimal_places=2, default=Decimal("0"), max_digits=14,
                    verbose_name="Montant déjà retenu")),
                ("prioritaire", models.BooleanField(
                    default=False,
                    verbose_name="Prioritaire (ex. pension alimentaire)")),
                ("date_debut", models.DateField(
                    verbose_name="Date de début de retenue")),
                ("actif", models.BooleanField(
                    default=True, verbose_name="Actif")),
                ("date_creation", models.DateTimeField(
                    auto_now_add=True, verbose_name="Créé le")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="paie_saisies",
                    to="authentication.company", verbose_name="Société")),
                ("profil", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="saisies", to="paie.profilpaie",
                    verbose_name="Profil de paie")),
            ],
            options={
                "verbose_name": "Saisie-arrêt / cession",
                "verbose_name_plural": "Saisies-arrêts / cessions",
                "ordering": ["-prioritaire", "date_debut", "id"],
            },
        ),
    ]
