# GED27 — Modèles de documents (fusion/mailing → PDF WeasyPrint, hors /proposal).
#
# Ajoute le modèle `ModeleDocument` : un gabarit company-scopé (nom, description,
# catégorie libre, corps HTML avec jetons `{{ champ }}`, drapeau `actif`) fusionné
# côté serveur avec un dictionnaire de données puis rendu en PDF via WeasyPrint
# (`services.rendre_modele`/`generer_document`). Couche GÉNÉRIQUE de documents
# INTERNES/administratifs (attestations, courriers, mailing), SÉPARÉE et
# DISTINCTE du chemin `/proposal` (rule #4) — qui reste l'unique chemin des PDF de
# devis client. Migration strictement additive ; aucune donnée existante touchée.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("ged", "0019_document_corbeille"),
    ]

    operations = [
        migrations.CreateModel(
            name="ModeleDocument",
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
                ("nom", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True, default="")),
                (
                    "categorie",
                    models.CharField(
                        blank=True, default="", max_length=80,
                        verbose_name="catégorie",
                    ),
                ),
                (
                    "corps_html",
                    models.TextField(
                        blank=True, default="",
                        verbose_name="corps HTML (avec {{ champs }})",
                    ),
                ),
                ("actif", models.BooleanField(default=True, verbose_name="actif")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "company",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ged_modeles_document",
                        to="authentication.company",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ged_modeles_document_crees",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Modèle de document",
                "verbose_name_plural": "Modèles de document",
                "ordering": ["nom", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="modeledocument",
            index=models.Index(
                fields=["company", "actif"], name="ged_modele_co_actif_idx"
            ),
        ),
    ]
