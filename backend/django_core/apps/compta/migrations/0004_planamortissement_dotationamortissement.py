# Generated for FG119 — plan d'amortissement + dotations.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0012_customuser_must_change_password_and_more"),
        ("compta", "0003_immobilisation"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlanAmortissement",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "mode",
                    models.CharField(
                        choices=[
                            ("lineaire", "Linéaire"),
                            ("degressif", "Dégressif"),
                        ],
                        default="lineaire",
                        max_length=10,
                        verbose_name="Mode d'amortissement",
                    ),
                ),
                (
                    "duree_annees",
                    models.PositiveIntegerField(verbose_name="Durée (années)"),
                ),
                (
                    "base_amortissable",
                    models.DecimalField(
                        decimal_places=2,
                        default=0,
                        max_digits=14,
                        verbose_name="Base amortissable (HT)",
                    ),
                ),
                (
                    "date_debut",
                    models.DateField(verbose_name="Date de début"),
                ),
                (
                    "coefficient_degressif",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=4,
                        null=True,
                        verbose_name="Coefficient dégressif",
                    ),
                ),
                (
                    "date_creation",
                    models.DateTimeField(auto_now_add=True, verbose_name="Créé le"),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="plans_amortissement",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "compte_amortissement",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="plans_amortissement_cumul",
                        to="compta.comptecomptable",
                        verbose_name="Compte d'amortissement (classe 28)",
                    ),
                ),
                (
                    "compte_dotation",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="plans_amortissement_dotation",
                        to="compta.comptecomptable",
                        verbose_name="Compte de dotation (classe 6)",
                    ),
                ),
                (
                    "immobilisation",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="plan_amortissement",
                        to="compta.immobilisation",
                        verbose_name="Immobilisation",
                    ),
                ),
            ],
            options={
                "verbose_name": "Plan d'amortissement",
                "verbose_name_plural": "Plans d'amortissement",
                "ordering": ["-date_creation", "-id"],
            },
        ),
        migrations.CreateModel(
            name="DotationAmortissement",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "annee",
                    models.PositiveIntegerField(verbose_name="Exercice (année)"),
                ),
                (
                    "date_dotation",
                    models.DateField(verbose_name="Date de dotation"),
                ),
                (
                    "montant",
                    models.DecimalField(
                        decimal_places=2,
                        default=0,
                        max_digits=14,
                        verbose_name="Dotation",
                    ),
                ),
                (
                    "cumul",
                    models.DecimalField(
                        decimal_places=2,
                        default=0,
                        max_digits=14,
                        verbose_name="Cumul des amortissements",
                    ),
                ),
                (
                    "valeur_nette",
                    models.DecimalField(
                        decimal_places=2,
                        default=0,
                        max_digits=14,
                        verbose_name="Valeur nette comptable",
                    ),
                ),
                (
                    "posted",
                    models.BooleanField(
                        default=False, verbose_name="Postée au grand livre"
                    ),
                ),
                (
                    "date_creation",
                    models.DateTimeField(auto_now_add=True, verbose_name="Créé le"),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="dotations_amortissement",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "ecriture",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="dotations_amortissement",
                        to="compta.ecriturecomptable",
                        verbose_name="Écriture comptable",
                    ),
                ),
                (
                    "plan",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="dotations",
                        to="compta.planamortissement",
                        verbose_name="Plan d'amortissement",
                    ),
                ),
            ],
            options={
                "verbose_name": "Dotation d'amortissement",
                "verbose_name_plural": "Dotations d'amortissement",
                "ordering": ["plan_id", "annee"],
            },
        ),
        migrations.AddConstraint(
            model_name="dotationamortissement",
            constraint=models.UniqueConstraint(
                fields=("plan", "annee"), name="uniq_dotation_par_plan_annee"
            ),
        ),
    ]
