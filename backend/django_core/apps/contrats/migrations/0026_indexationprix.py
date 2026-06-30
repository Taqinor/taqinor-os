"""Migration additive : modèle ``IndexationPrix``
(CONTRAT32 — indexation / révision de prix).

Entièrement additive (``CreateModel`` + index) — réversible via ``DeleteModel``.
Une ``IndexationPrix`` déclare une règle de révision du prix d'un ``Contrat`` par
indice (``indice``, ``valeur_base``, ``part_fixe``). Le calcul
(``services.calculer_prix_indexe``) est purement déclaratif ; l'application
(``services.appliquer_indexation``) passe par un AVENANT (CONTRAT24) ajustant
``Contrat.montant`` — le ``Contrat.statut`` n'est jamais modifié (CONTRAT12) ni
le funnel ``STAGES.py`` (rule #2). La société est posée côté serveur.

RUNTIME-SAFETY (leçon FG136) : ``libelle`` / ``indice`` bornés ; l'index est
nommé explicitement (≤30 chars).
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contrats", "0025_facturation_recurrente"),
    ]

    operations = [
        migrations.CreateModel(
            name="IndexationPrix",
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
                    "libelle",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=200,
                        verbose_name="Libellé",
                    ),
                ),
                (
                    "indice",
                    models.CharField(
                        max_length=100, verbose_name="Indice de référence"
                    ),
                ),
                (
                    "valeur_base",
                    models.DecimalField(
                        decimal_places=4,
                        default=0,
                        max_digits=14,
                        verbose_name="Valeur de base",
                    ),
                ),
                (
                    "part_fixe",
                    models.DecimalField(
                        decimal_places=4,
                        default=0,
                        max_digits=5,
                        verbose_name="Part fixe (0–1)",
                    ),
                ),
                (
                    "periodicite",
                    models.CharField(
                        choices=[
                            ("annuelle", "Annuelle"),
                            ("semestrielle", "Semestrielle"),
                            ("trimestrielle", "Trimestrielle"),
                            ("a_la_demande", "À la demande"),
                        ],
                        default="annuelle",
                        max_length=20,
                        verbose_name="Périodicité de révision",
                    ),
                ),
                (
                    "date_derniere_revision",
                    models.DateField(
                        blank=True,
                        null=True,
                        verbose_name="Dernière révision le",
                    ),
                ),
                (
                    "actif",
                    models.BooleanField(default=True, verbose_name="Actif"),
                ),
                (
                    "date_creation",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Créée le"
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="contrats_indexations",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "contrat",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="indexations",
                        to="contrats.contrat",
                        verbose_name="Contrat",
                    ),
                ),
            ],
            options={
                "verbose_name": "Indexation de prix",
                "verbose_name_plural": "Indexations de prix",
                "ordering": ["contrat_id", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="indexationprix",
            index=models.Index(
                fields=["company", "actif"],
                name="contrats_idx_co_act",
            ),
        ),
    ]
