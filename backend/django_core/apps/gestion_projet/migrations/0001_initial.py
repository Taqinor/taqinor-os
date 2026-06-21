import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("authentication", "0008_customuser_avatar_key_customuser_poste"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Projet",
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
                ("code", models.CharField(max_length=30, verbose_name="Code")),
                ("nom", models.CharField(max_length=200, verbose_name="Nom")),
                (
                    "description",
                    models.TextField(
                        blank=True, default="", verbose_name="Description"
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("prospect", "Prospect"),
                            ("en_cours", "En cours"),
                            ("suspendu", "Suspendu"),
                            ("termine", "Terminé"),
                            ("annule", "Annulé"),
                        ],
                        default="en_cours",
                        max_length=10,
                        verbose_name="Statut",
                    ),
                ),
                (
                    "client_id",
                    models.PositiveIntegerField(
                        blank=True, null=True, verbose_name="ID du client"
                    ),
                ),
                (
                    "date_debut",
                    models.DateField(
                        blank=True, null=True, verbose_name="Date de début"
                    ),
                ),
                (
                    "date_fin_prevue",
                    models.DateField(
                        blank=True, null=True, verbose_name="Date de fin prévue"
                    ),
                ),
                (
                    "budget_total",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=14,
                        verbose_name="Budget total",
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
                        related_name="projets",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "responsable",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="projets_responsable",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Responsable",
                    ),
                ),
            ],
            options={
                "verbose_name": "Projet",
                "verbose_name_plural": "Projets",
                "ordering": ["-id"],
            },
        ),
        migrations.CreateModel(
            name="ProjetChantier",
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
                    "chantier_id",
                    models.PositiveIntegerField(verbose_name="ID du chantier"),
                ),
                (
                    "libelle",
                    models.CharField(
                        blank=True, default="", max_length=200, verbose_name="Libellé"
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
                        related_name="projet_chantiers",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "projet",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chantiers",
                        to="gestion_projet.projet",
                        verbose_name="Projet",
                    ),
                ),
            ],
            options={
                "verbose_name": "Chantier du projet",
                "verbose_name_plural": "Chantiers du projet",
                "ordering": ["id"],
            },
        ),
        migrations.AlterUniqueTogether(
            name="projet",
            unique_together={("company", "code")},
        ),
    ]
