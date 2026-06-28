# Generated manually for PROJ15 — Profil ressource & équipes (RH-léger)

import decimal
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0012_customuser_must_change_password_and_more"),
        ("gestion_projet", "0009_baselineplanning_baselinetache_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="RessourceProfil",
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
                    "nom",
                    models.CharField(max_length=150, verbose_name="Nom / identifiant"),
                ),
                (
                    "role",
                    models.CharField(
                        blank=True, default="", max_length=100, verbose_name="Rôle"
                    ),
                ),
                (
                    "competences",
                    models.TextField(
                        blank=True, default="", verbose_name="Compétences"
                    ),
                ),
                (
                    "cout_horaire",
                    models.DecimalField(
                        decimal_places=2,
                        default=decimal.Decimal("0"),
                        max_digits=10,
                        verbose_name="Coût horaire interne",
                    ),
                ),
                (
                    "actif",
                    models.BooleanField(default=True, verbose_name="Actif"),
                ),
                (
                    "date_creation",
                    models.DateTimeField(auto_now_add=True, verbose_name="Créé le"),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="projet_ressources",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="gestion_projet_ressources",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Utilisateur lié",
                    ),
                ),
            ],
            options={
                "verbose_name": "Profil ressource",
                "verbose_name_plural": "Profils ressources",
                "ordering": ["nom", "id"],
            },
        ),
        migrations.AddConstraint(
            model_name="ressourceprofil",
            constraint=models.UniqueConstraint(
                fields=["company", "nom"],
                name="gp_ressource_company_nom_uniq",
            ),
        ),
        migrations.CreateModel(
            name="Equipe",
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
                    "nom",
                    models.CharField(
                        max_length=150, verbose_name="Nom de l'équipe"
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        blank=True, default="", verbose_name="Description"
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
                        related_name="projet_equipes",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "membres",
                    models.ManyToManyField(
                        blank=True,
                        related_name="equipes",
                        to="gestion_projet.ressourceprofil",
                        verbose_name="Membres",
                    ),
                ),
            ],
            options={
                "verbose_name": "Équipe",
                "verbose_name_plural": "Équipes",
                "ordering": ["nom", "id"],
            },
        ),
        migrations.AddConstraint(
            model_name="equipe",
            constraint=models.UniqueConstraint(
                fields=["company", "nom"],
                name="gp_equipe_company_nom_uniq",
            ),
        ),
    ]
