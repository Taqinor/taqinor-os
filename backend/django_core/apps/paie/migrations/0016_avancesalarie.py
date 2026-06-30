# Generated manually — PAIE28 Avance / prêt salarié + déduction mensuelle.
#
# Additive : nouveau modèle ``AvanceSalarie`` (avance ponctuelle ou prêt étalé)
# remboursé par retenue mensuelle sur le bulletin. Aucun comportement existant
# modifié — la retenue ne s'applique qu'aux avances actives non soldées.

from decimal import Decimal

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """PAIE28 — Avance / prêt salarié remboursé par déduction mensuelle."""

    dependencies = [
        ("paie", "0015_cumulannuel"),
    ]

    operations = [
        migrations.CreateModel(
            name="AvanceSalarie",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("type", models.CharField(
                    choices=[("avance", "Avance sur salaire"),
                             ("pret", "Prêt salarié")],
                    default="avance", max_length=10, verbose_name="Type")),
                ("libelle", models.CharField(
                    blank=True, default="", max_length=120,
                    verbose_name="Libellé")),
                ("montant_total", models.DecimalField(
                    decimal_places=2, default=Decimal("0"), max_digits=14,
                    verbose_name="Montant total accordé")),
                ("montant_echeance", models.DecimalField(
                    decimal_places=2, default=Decimal("0"), max_digits=14,
                    verbose_name="Montant de l'échéance mensuelle")),
                ("nombre_echeances", models.PositiveSmallIntegerField(
                    default=1, verbose_name="Nombre d'échéances")),
                ("montant_rembourse", models.DecimalField(
                    decimal_places=2, default=Decimal("0"), max_digits=14,
                    verbose_name="Montant déjà remboursé")),
                ("date_debut", models.DateField(
                    verbose_name="Date de début de retenue")),
                ("actif", models.BooleanField(
                    default=True, verbose_name="Actif")),
                ("date_creation", models.DateTimeField(
                    auto_now_add=True, verbose_name="Créé le")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="paie_avances",
                    to="authentication.company", verbose_name="Société")),
                ("profil", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="avances", to="paie.profilpaie",
                    verbose_name="Profil de paie")),
            ],
            options={
                "verbose_name": "Avance / prêt salarié",
                "verbose_name_plural": "Avances / prêts salariés",
                "ordering": ["-date_creation"],
            },
        ),
    ]
