# Generated for FLOTTE22 — visite technique. Ajoute le modèle
# ``VisiteTechnique`` (passage en centre de contrôle technique : centre, date de
# visite, résultat, validité PARAMÉTRABLE en mois, prochaine visite calculée).
# Modèle DÉDIÉ au PASSAGE, qui COMPLÈTE sans la dupliquer
# l'``EcheanceReglementaire`` générique (FLOTTE19). Additif, multi-société.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0013_customuser_poste_ref"),
        ("flotte", "0019_assurancevehicule"),
    ]

    operations = [
        migrations.CreateModel(
            name="VisiteTechnique",
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
                    "centre",
                    models.CharField(
                        max_length=120, verbose_name="Centre de visite"
                    ),
                ),
                (
                    "date_visite",
                    models.DateField(verbose_name="Date de la visite"),
                ),
                (
                    "resultat",
                    models.CharField(
                        choices=[
                            ("favorable", "Favorable"),
                            ("defavorable", "Défavorable"),
                            ("contre_visite", "Contre-visite"),
                        ],
                        default="favorable",
                        max_length=16,
                        verbose_name="Résultat",
                    ),
                ),
                (
                    "validite_mois",
                    models.PositiveIntegerField(
                        default=12, verbose_name="Validité (mois)"
                    ),
                ),
                (
                    "date_prochaine",
                    models.DateField(
                        blank=True, null=True,
                        verbose_name="Prochaine visite",
                    ),
                ),
                (
                    "cout",
                    models.DecimalField(
                        decimal_places=2, default=0, max_digits=12,
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
                            ("valide", "Valide"),
                            ("a_renouveler", "À renouveler"),
                            ("expiree", "Expirée"),
                        ],
                        default="valide",
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
                    "actif_flotte",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="flotte_visites_techniques",
                        to="flotte.actifflotte",
                        verbose_name="Actif (véhicule ou engin)",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="flotte_visites_techniques",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
            ],
            options={
                "verbose_name": "Visite technique",
                "verbose_name_plural": "Visites techniques",
                "ordering": ["date_prochaine", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="visitetechnique",
            index=models.Index(
                fields=["company", "statut"],
                name="flotte_vistec_co_stat_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="visitetechnique",
            index=models.Index(
                fields=["company", "actif_flotte"],
                name="flotte_vistec_co_actif_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="visitetechnique",
            index=models.Index(
                fields=["company", "date_prochaine"],
                name="flotte_vistec_co_proch_idx",
            ),
        ),
    ]
