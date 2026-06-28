# Generated manually for PROJ16 -- Affectation des ressources

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0012_customuser_must_change_password_and_more"),
        ("gestion_projet", "0010_ressourceprofil_equipe"),
    ]

    operations = [
        migrations.CreateModel(
            name="AffectationRessource",
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
                    "actif_type",
                    models.CharField(
                        blank=True,
                        choices=[("actif_flotte", "Actif flotte")],
                        default="",
                        max_length=30,
                        verbose_name="Type actif",
                    ),
                ),
                (
                    "actif_id",
                    models.PositiveIntegerField(
                        blank=True, null=True, verbose_name="ID de l'actif"
                    ),
                ),
                (
                    "date_debut",
                    models.DateField(verbose_name="Date de debut"),
                ),
                (
                    "date_fin",
                    models.DateField(verbose_name="Date de fin"),
                ),
                (
                    "charge_jours",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=8,
                        null=True,
                        verbose_name="Charge (j-h)",
                    ),
                ),
                (
                    "quantite",
                    models.DecimalField(
                        blank=True,
                        decimal_places=3,
                        max_digits=10,
                        null=True,
                        verbose_name="Quantite",
                    ),
                ),
                (
                    "note",
                    models.TextField(blank=True, default="", verbose_name="Note"),
                ),
                (
                    "date_creation",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Cree le"
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="gp_affectations",
                        to="authentication.company",
                        verbose_name="Societe",
                    ),
                ),
                (
                    "tache",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="affectations",
                        to="gestion_projet.tache",
                        verbose_name="Tache",
                    ),
                ),
                (
                    "ressource",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="gp_affectations",
                        to="gestion_projet.ressourceprofil",
                        verbose_name="Ressource (profil)",
                    ),
                ),
                (
                    "equipe",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="gp_affectations",
                        to="gestion_projet.equipe",
                        verbose_name="Equipe",
                    ),
                ),
            ],
            options={
                "verbose_name": "Affectation de ressource",
                "verbose_name_plural": "Affectations de ressources",
                "ordering": ["tache", "date_debut", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="affectationressource",
            index=models.Index(
                fields=["tache", "date_debut"],
                name="gp_affect_tache_debut_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="affectationressource",
            index=models.Index(
                fields=["ressource"],
                name="gp_affect_ressource_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="affectationressource",
            index=models.Index(
                fields=["equipe"],
                name="gp_affect_equipe_idx",
            ),
        ),
    ]
