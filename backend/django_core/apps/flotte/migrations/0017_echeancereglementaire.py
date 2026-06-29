# Generated for FLOTTE19 — EcheanceReglementaire (échéances réglementaires /
# administratives des actifs de flotte : visite technique, assurance, vignette,
# carte grise, taxe à l'essieu…). Modèle additif, multi-société.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0013_customuser_poste_ref"),
        ("flotte", "0016_pneumatique_pieceflotte"),
    ]

    operations = [
        migrations.CreateModel(
            name="EcheanceReglementaire",
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
                    "type_echeance",
                    models.CharField(
                        choices=[
                            ("visite_technique", "Visite technique"),
                            ("assurance", "Assurance"),
                            ("vignette", "Vignette / TSAV"),
                            ("carte_grise", "Carte grise"),
                            ("taxe_essieu", "Taxe à l'essieu"),
                            ("autre", "Autre"),
                        ],
                        default="visite_technique",
                        max_length=20,
                        verbose_name="Type d'échéance",
                    ),
                ),
                (
                    "date_echeance",
                    models.DateField(verbose_name="Date d'échéance"),
                ),
                (
                    "date_dernier_renouvellement",
                    models.DateField(
                        blank=True,
                        null=True,
                        verbose_name="Dernier renouvellement",
                    ),
                ),
                (
                    "organisme",
                    models.CharField(
                        blank=True, max_length=120, verbose_name="Organisme"
                    ),
                ),
                (
                    "cout",
                    models.DecimalField(
                        decimal_places=2,
                        default=0,
                        max_digits=12,
                        verbose_name="Coût (MAD)",
                    ),
                ),
                (
                    "alerte_jours",
                    models.PositiveIntegerField(
                        default=30, verbose_name="Marge d'alerte (jours)"
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("a_jour", "À jour"),
                            ("a_renouveler", "À renouveler"),
                            ("expire", "Expiré"),
                        ],
                        default="a_jour",
                        max_length=12,
                        verbose_name="Statut",
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
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="flotte_echeances_reglementaires",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "actif_flotte",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="flotte_echeances_reglementaires",
                        to="flotte.actifflotte",
                        verbose_name="Actif (véhicule ou engin)",
                    ),
                ),
            ],
            options={
                "verbose_name": "Échéance réglementaire",
                "verbose_name_plural": "Échéances réglementaires",
                "ordering": ["date_echeance", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="echeancereglementaire",
            index=models.Index(
                fields=["company", "statut"],
                name="flotte_echreg_co_stat_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="echeancereglementaire",
            index=models.Index(
                fields=["company", "actif_flotte"],
                name="flotte_echreg_co_actif_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="echeancereglementaire",
            index=models.Index(
                fields=["company", "date_echeance"],
                name="flotte_echreg_co_date_idx",
            ),
        ),
    ]
