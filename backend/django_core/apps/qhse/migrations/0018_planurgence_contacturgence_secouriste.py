# Generated for QHSE28 — Plan d'urgence / premiers secours par chantier/site.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0012_customuser_must_change_password_and_more"),
        ("rh", "0023_causerie_securite"),
        ("qhse", "0017_inductionsecurite"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlanUrgence",
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
                    models.PositiveIntegerField(
                        blank=True, null=True,
                        verbose_name="ID du chantier",
                    ),
                ),
                (
                    "titre",
                    models.CharField(max_length=255, verbose_name="Titre"),
                ),
                (
                    "point_rassemblement",
                    models.CharField(
                        blank=True, default="", max_length=255,
                        verbose_name="Point de rassemblement",
                    ),
                ),
                (
                    "point_rassemblement_details",
                    models.TextField(
                        blank=True, default="",
                        verbose_name="Point de rassemblement (détails)",
                    ),
                ),
                (
                    "hopital_proche",
                    models.CharField(
                        blank=True, default="", max_length=255,
                        verbose_name="Hôpital le plus proche",
                    ),
                ),
                (
                    "hopital_distance_km",
                    models.DecimalField(
                        blank=True, decimal_places=2, max_digits=6,
                        null=True, verbose_name="Distance hôpital (km)",
                    ),
                ),
                (
                    "hopital_telephone",
                    models.CharField(
                        blank=True, default="", max_length=40,
                        verbose_name="Téléphone hôpital",
                    ),
                ),
                (
                    "date_revision",
                    models.DateField(
                        blank=True, null=True,
                        verbose_name="Date de révision",
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("brouillon", "Brouillon"),
                            ("actif", "Actif"),
                            ("archive", "Archivé"),
                        ],
                        default="brouillon",
                        max_length=10,
                        verbose_name="Statut",
                    ),
                ),
                (
                    "notes",
                    models.TextField(
                        blank=True, default="", verbose_name="Notes"
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
                        related_name="qhse_plans_urgence",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
            ],
            options={
                "verbose_name": "Plan d'urgence / premiers secours",
                "verbose_name_plural": "Plans d'urgence / premiers secours",
                "ordering": ["-id"],
            },
        ),
        migrations.CreateModel(
            name="ContactUrgence",
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
                    "type_contact",
                    models.CharField(
                        choices=[
                            ("pompiers", "Pompiers"),
                            ("samu", "SAMU / urgences médicales"),
                            ("police", "Police / gendarmerie"),
                            ("interne", "Contact interne"),
                            ("autre", "Autre"),
                        ],
                        default="autre",
                        max_length=10,
                        verbose_name="Type de contact",
                    ),
                ),
                (
                    "nom",
                    models.CharField(
                        max_length=255, verbose_name="Nom / service"
                    ),
                ),
                (
                    "telephone",
                    models.CharField(
                        max_length=40, verbose_name="Téléphone"
                    ),
                ),
                (
                    "notes",
                    models.CharField(
                        blank=True, default="", max_length=255,
                        verbose_name="Notes",
                    ),
                ),
                (
                    "ordre",
                    models.PositiveIntegerField(
                        default=0, verbose_name="Ordre"
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
                        related_name="qhse_contacts_urgence",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "plan",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="contacts",
                        to="qhse.planurgence",
                        verbose_name="Plan d'urgence",
                    ),
                ),
            ],
            options={
                "verbose_name": "Contact d'urgence",
                "verbose_name_plural": "Contacts d'urgence",
                "ordering": ["plan", "ordre", "id"],
            },
        ),
        migrations.CreateModel(
            name="Secouriste",
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
                        blank=True, default="", max_length=255,
                        verbose_name="Nom (si externe)",
                    ),
                ),
                (
                    "telephone",
                    models.CharField(
                        blank=True, default="", max_length=40,
                        verbose_name="Téléphone",
                    ),
                ),
                (
                    "certification",
                    models.CharField(
                        blank=True, default="", max_length=255,
                        verbose_name="Certification (SST…)",
                    ),
                ),
                (
                    "validite",
                    models.DateField(
                        blank=True, null=True,
                        verbose_name="Validité certification",
                    ),
                ),
                (
                    "ordre",
                    models.PositiveIntegerField(
                        default=0, verbose_name="Ordre"
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
                        related_name="qhse_secouristes",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "plan",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="secouristes",
                        to="qhse.planurgence",
                        verbose_name="Plan d'urgence",
                    ),
                ),
                (
                    "secouriste",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="qhse_secouristes",
                        to="rh.dossieremploye",
                        verbose_name="Salarié (dossier RH)",
                    ),
                ),
            ],
            options={
                "verbose_name": "Secouriste désigné",
                "verbose_name_plural": "Secouristes désignés",
                "ordering": ["plan", "ordre", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="planurgence",
            index=models.Index(
                fields=["company", "chantier_id"],
                name="qhse_planurg_co_chant",
            ),
        ),
        migrations.AddIndex(
            model_name="planurgence",
            index=models.Index(
                fields=["company", "statut"],
                name="qhse_planurg_co_statut",
            ),
        ),
        migrations.AddIndex(
            model_name="contacturgence",
            index=models.Index(
                fields=["company", "plan"],
                name="qhse_conturg_co_plan",
            ),
        ),
        migrations.AddIndex(
            model_name="secouriste",
            index=models.Index(
                fields=["company", "plan"],
                name="qhse_secour_co_plan",
            ),
        ),
    ]
