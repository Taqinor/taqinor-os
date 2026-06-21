import django.db.models.deletion
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
            name="Dossier",
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
                ("nom", models.CharField(max_length=200, verbose_name="Nom")),
                (
                    "chemin",
                    models.CharField(
                        blank=True, default="", max_length=500, verbose_name="Chemin"
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
                        related_name="ged_dossiers",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="enfants",
                        to="ged.dossier",
                        verbose_name="Dossier parent",
                    ),
                ),
            ],
            options={
                "verbose_name": "Dossier",
                "verbose_name_plural": "Dossiers",
                "ordering": ["chemin", "nom"],
            },
        ),
        migrations.CreateModel(
            name="Document",
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
                ("titre", models.CharField(max_length=255, verbose_name="Titre")),
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
                            ("brouillon", "Brouillon"),
                            ("publie", "Publié"),
                            ("archive", "Archivé"),
                        ],
                        default="brouillon",
                        max_length=15,
                        verbose_name="Statut",
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
                        related_name="ged_documents",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ged_documents_crees",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Créé par",
                    ),
                ),
                (
                    "dossier",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="documents",
                        to="ged.dossier",
                        verbose_name="Dossier",
                    ),
                ),
            ],
            options={
                "verbose_name": "Document",
                "verbose_name_plural": "Documents",
                "ordering": ["-id"],
            },
        ),
        migrations.CreateModel(
            name="DocumentVersion",
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
                    "numero_version",
                    models.PositiveIntegerField(
                        default=1, verbose_name="Numéro de version"
                    ),
                ),
                (
                    "file_key",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=255,
                        verbose_name="Clé objet MinIO",
                    ),
                ),
                (
                    "filename",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=255,
                        verbose_name="Nom de fichier",
                    ),
                ),
                (
                    "mime",
                    models.CharField(
                        blank=True, default="", max_length=120, verbose_name="Type MIME"
                    ),
                ),
                (
                    "taille",
                    models.PositiveIntegerField(default=0, verbose_name="Taille"),
                ),
                (
                    "checksum",
                    models.CharField(
                        blank=True, default="", max_length=64, verbose_name="Checksum"
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
                        related_name="ged_versions",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="versions",
                        to="ged.document",
                        verbose_name="Document",
                    ),
                ),
            ],
            options={
                "verbose_name": "Version de document",
                "verbose_name_plural": "Versions de document",
                "ordering": ["-numero_version"],
                "unique_together": {("document", "numero_version")},
            },
        ),
    ]
