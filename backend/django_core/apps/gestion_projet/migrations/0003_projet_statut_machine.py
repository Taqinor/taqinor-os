# Generated for PROJ3 — machine à états du projet (additif, revertable).
#
# Reprofile ``Projet.statut`` sur le cycle de vie PROPRE au projet (brouillon →
# planifie → en_cours → en_pause → termine / annule ; défaut ``brouillon``) et
# ajoute le journal minimal des transitions ``ProjetActivity``. Le ``AlterField``
# est sûr : ``statut`` garde un défaut scalaire (aucun piège unique/sans-défaut).

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0008_customuser_avatar_key_customuser_poste"),
        ("gestion_projet", "0002_projetlien"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="projet",
            name="statut",
            field=models.CharField(
                choices=[
                    ("brouillon", "Brouillon"),
                    ("planifie", "Planifié"),
                    ("en_cours", "En cours"),
                    ("en_pause", "En pause"),
                    ("termine", "Terminé"),
                    ("annule", "Annulé"),
                ],
                default="brouillon",
                max_length=15,
                verbose_name="Statut",
            ),
        ),
        migrations.CreateModel(
            name="ProjetActivity",
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
                    "old_value",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=15,
                        verbose_name="Ancien statut",
                    ),
                ),
                (
                    "new_value",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=15,
                        verbose_name="Nouveau statut",
                    ),
                ),
                (
                    "date_creation",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Créé le"
                    ),
                ),
                (
                    "auteur",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="projet_activites",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Auteur",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="projet_activites",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "projet",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="activites",
                        to="gestion_projet.projet",
                        verbose_name="Projet",
                    ),
                ),
            ],
            options={
                "verbose_name": "Activité projet",
                "verbose_name_plural": "Activités projet",
                "ordering": ["-date_creation", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="projetactivity",
            index=models.Index(
                fields=["projet", "-date_creation"],
                name="gp_proj_activity_idx",
            ),
        ),
    ]
