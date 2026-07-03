# Generated for XFLT18 — Budget flotte annuel vs réalisé. Crée
# ``BudgetFlotte`` (une ligne par société+année+catégorie). Additif,
# multi-société.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("flotte", "0042_charte_vehicule"),
    ]

    operations = [
        migrations.CreateModel(
            name="BudgetFlotte",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("annee", models.PositiveSmallIntegerField(
                    verbose_name="Année")),
                ("categorie", models.CharField(
                    choices=[
                        ("carburant", "Carburant"),
                        ("entretien", "Entretien"),
                        ("assurance", "Assurance"),
                        ("vignette", "Vignette"),
                        ("contrat", "Contrat"),
                        ("autre", "Autre"),
                    ], default="autre", max_length=10,
                    verbose_name="Catégorie")),
                ("montant_budgete", models.DecimalField(
                    decimal_places=2, default=0, max_digits=12,
                    verbose_name="Montant budgété (MAD)")),
                ("notifie_depassement", models.BooleanField(
                    default=False, verbose_name="Dépassement déjà notifié")),
                ("date_creation", models.DateTimeField(
                    auto_now_add=True, verbose_name="Créé le")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="flotte_budgets",
                    to="authentication.company", verbose_name="Société")),
            ],
            options={
                "verbose_name": "Budget flotte",
                "verbose_name_plural": "Budgets flotte",
                "ordering": ["-annee", "categorie"],
            },
        ),
        migrations.AddConstraint(
            model_name="budgetflotte",
            constraint=models.UniqueConstraint(
                fields=("company", "annee", "categorie"),
                name="flotte_budgetflotte_co_an_cat_uniq"),
        ),
    ]
