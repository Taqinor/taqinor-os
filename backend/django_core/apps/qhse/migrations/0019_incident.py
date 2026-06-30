# Generated for QHSE29 — Registre Incident HSE (accident/presqu'accident/incident).

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0012_customuser_must_change_password_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("qhse", "0018_planurgence_contacturgence_secouriste"),
    ]

    operations = [
        migrations.CreateModel(
            name="Incident",
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
                    "reference",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=50,
                        verbose_name="Référence",
                    ),
                ),
                ("titre", models.CharField(max_length=255, verbose_name="Titre")),
                (
                    "type_incident",
                    models.CharField(
                        choices=[
                            ("accident", "Accident"),
                            ("presqu_accident", "Presqu’accident"),
                            ("incident", "Incident"),
                        ],
                        default="incident",
                        max_length=20,
                        verbose_name="Type d'événement",
                    ),
                ),
                (
                    "gravite",
                    models.CharField(
                        choices=[
                            ("mineure", "Mineure"),
                            ("majeure", "Majeure"),
                            ("critique", "Critique"),
                        ],
                        default="mineure",
                        max_length=10,
                        verbose_name="Gravité",
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("ouvert", "Ouvert"),
                            ("en_cours", "En cours"),
                            ("clos", "Clos"),
                        ],
                        default="ouvert",
                        max_length=10,
                        verbose_name="Statut",
                    ),
                ),
                (
                    "chantier_id",
                    models.PositiveIntegerField(
                        blank=True, null=True, verbose_name="ID du chantier"
                    ),
                ),
                (
                    "date_incident",
                    models.DateField(
                        blank=True, null=True, verbose_name="Date de l'événement"
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        blank=True, default="", verbose_name="Description"
                    ),
                ),
                (
                    "action_immediate",
                    models.TextField(
                        blank=True, default="", verbose_name="Action immédiate"
                    ),
                ),
                (
                    "date_creation",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Créé le"
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="qhse_incidents",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "declare_par",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="qhse_incidents_declares",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Déclaré par",
                    ),
                ),
            ],
            options={
                "verbose_name": "Incident HSE",
                "verbose_name_plural": "Incidents HSE",
                "ordering": ["-id"],
            },
        ),
        migrations.AddConstraint(
            model_name="incident",
            constraint=models.UniqueConstraint(
                fields=("company", "reference"),
                name="qhse_incident_co_ref_uniq",
            ),
        ),
        migrations.AddIndex(
            model_name="incident",
            index=models.Index(
                fields=["company", "statut"], name="qhse_incident_co_statut"
            ),
        ),
        migrations.AddIndex(
            model_name="incident",
            index=models.Index(
                fields=["company", "type_incident"],
                name="qhse_incident_co_type",
            ),
        ),
        migrations.AddIndex(
            model_name="incident",
            index=models.Index(
                fields=["company", "chantier_id"],
                name="qhse_incident_co_chant",
            ),
        ),
    ]
