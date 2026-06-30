# Generated for FLOTTE25 — sinistres. Ajoute le modèle ``Sinistre``
# (accident / constat / assurance) : actif lié, date, type, description, lieu,
# constat amiable scanné, police d'assurance liée (AssuranceVehicule, FLOTTE21,
# même app, facultative), numéro de déclaration, montants (estimé, franchise),
# statut (déclaré/en cours/clos/indemnisé). Additif, multi-société.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0013_customuser_poste_ref"),
        ("flotte", "0021_cartegrisevehicule"),
    ]

    operations = [
        migrations.CreateModel(
            name="Sinistre",
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
                    "date_sinistre",
                    models.DateField(verbose_name="Date du sinistre"),
                ),
                (
                    "type_sinistre",
                    models.CharField(
                        choices=[
                            ("accident_materiel", "Accident matériel"),
                            ("accident_corporel", "Accident corporel"),
                            ("vol", "Vol"),
                            ("bris_de_glace", "Bris de glace"),
                            ("incendie", "Incendie"),
                            ("catastrophe", "Catastrophe naturelle"),
                            ("autre", "Autre"),
                        ],
                        default="accident_materiel",
                        max_length=20,
                        verbose_name="Type de sinistre",
                    ),
                ),
                (
                    "description",
                    models.TextField(verbose_name="Description"),
                ),
                (
                    "lieu",
                    models.CharField(
                        blank=True, max_length=255, verbose_name="Lieu"
                    ),
                ),
                (
                    "constat_fichier",
                    models.FileField(
                        blank=True,
                        null=True,
                        upload_to="flotte/sinistres/constats/%Y/%m/",
                        verbose_name="Constat amiable",
                    ),
                ),
                (
                    "numero_declaration",
                    models.CharField(
                        blank=True,
                        max_length=80,
                        verbose_name="Numéro de déclaration",
                    ),
                ),
                (
                    "montant_estime",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=12,
                        null=True,
                        verbose_name="Montant estimé des dommages (MAD)",
                    ),
                ),
                (
                    "franchise",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=12,
                        null=True,
                        verbose_name="Franchise à charge (MAD)",
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("declare", "Déclaré"),
                            ("en_cours", "En cours"),
                            ("clos", "Clos"),
                            ("indemnise", "Indemnisé"),
                        ],
                        default="declare",
                        max_length=9,
                        verbose_name="Statut",
                    ),
                ),
                (
                    "date_declaration",
                    models.DateField(
                        blank=True,
                        null=True,
                        verbose_name="Date de déclaration",
                    ),
                ),
                ("notes", models.TextField(blank=True, verbose_name="Notes")),
                (
                    "date_creation",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Créé le"
                    ),
                ),
                (
                    "actif_flotte",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="flotte_sinistres",
                        to="flotte.actifflotte",
                        verbose_name="Actif (véhicule ou engin)",
                    ),
                ),
                (
                    "assurance",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="flotte_sinistres",
                        to="flotte.assurancevehicule",
                        verbose_name="Police d'assurance liée",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="flotte_sinistres",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
            ],
            options={
                "verbose_name": "Sinistre",
                "verbose_name_plural": "Sinistres",
                "ordering": ["-date_sinistre", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="sinistre",
            index=models.Index(
                fields=["company", "statut"],
                name="flotte_sin_co_stat_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="sinistre",
            index=models.Index(
                fields=["company", "actif_flotte"],
                name="flotte_sin_co_actif_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="sinistre",
            index=models.Index(
                fields=["company", "type_sinistre"],
                name="flotte_sin_co_type_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="sinistre",
            index=models.Index(
                fields=["company", "date_sinistre"],
                name="flotte_sin_co_date_idx",
            ),
        ),
    ]
