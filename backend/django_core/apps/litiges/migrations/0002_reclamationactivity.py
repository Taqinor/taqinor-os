# Generated for LITIGE2 — chatter d'une réclamation (additif).

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("litiges", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ReclamationActivity",
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
                    "type",
                    models.CharField(
                        choices=[
                            ("log", "Changement de statut"),
                            ("note", "Note"),
                        ],
                        max_length=10,
                        verbose_name="Type",
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
                    "message",
                    models.TextField(
                        blank=True, default="", verbose_name="Message"
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
                        related_name="litiges_activites",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Auteur",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="litiges_activites",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "reclamation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="activites",
                        to="litiges.reclamation",
                        verbose_name="Réclamation",
                    ),
                ),
            ],
            options={
                "verbose_name": "Activité réclamation",
                "verbose_name_plural": "Activités réclamation",
                "ordering": ["-date_creation", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="reclamationactivity",
            index=models.Index(
                fields=["reclamation", "-date_creation"],
                name="litiges_rec_reclama_idx",
            ),
        ),
    ]
