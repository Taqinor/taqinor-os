"""Migration additive : modèle ``EngagementSLA``
(CONTRAT27 — SLA & pénalités : taux cible, valeur de pénalité).

Entièrement additive (``CreateModel`` + index) — réversible via ``DeleteModel``.
Un ``EngagementSLA`` déclare un objectif de service chiffré (``taux_cible``) pour
un ``Contrat`` et la pénalité encourue (montant fixe ou pourcentage du montant du
contrat, plafonné par ``penalite_max``). Le calcul de pénalité
(``services.calculer_penalite_sla``) est purement déclaratif : il ne crée aucune
écriture, ne touche aucun ``Contrat.statut`` (CONTRAT12) ni le funnel
``STAGES.py`` (rule #2), et n'émet aucune facture. La société est posée côté
serveur (déduite du contrat).

RUNTIME-SAFETY (leçon FG136) : ``libelle`` borné (≤200), ``unite`` borné (≤30) ;
l'index est nommé explicitement (≤30 chars).
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contrats", "0020_jalon_obligation"),
    ]

    operations = [
        migrations.CreateModel(
            name="EngagementSLA",
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
                        max_length=200, verbose_name="Libellé du SLA"
                    ),
                ),
                (
                    "taux_cible",
                    models.DecimalField(
                        decimal_places=2,
                        default=0,
                        max_digits=6,
                        verbose_name="Taux cible (%)",
                    ),
                ),
                (
                    "unite",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=30,
                        verbose_name="Unité / métrique",
                    ),
                ),
                (
                    "mode_penalite",
                    models.CharField(
                        choices=[
                            ("fixe", "Montant fixe"),
                            (
                                "pourcentage",
                                "Pourcentage du montant du contrat",
                            ),
                        ],
                        default="fixe",
                        max_length=20,
                        verbose_name="Mode de pénalité",
                    ),
                ),
                (
                    "valeur_penalite",
                    models.DecimalField(
                        decimal_places=2,
                        default=0,
                        max_digits=14,
                        verbose_name="Valeur de la pénalité",
                    ),
                ),
                (
                    "penalite_max",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=14,
                        null=True,
                        verbose_name="Plafond de pénalité",
                    ),
                ),
                (
                    "actif",
                    models.BooleanField(default=True, verbose_name="Actif"),
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
                        related_name="contrats_sla",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "contrat",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="engagements_sla",
                        to="contrats.contrat",
                        verbose_name="Contrat",
                    ),
                ),
            ],
            options={
                "verbose_name": "Engagement SLA",
                "verbose_name_plural": "Engagements SLA",
                "ordering": ["contrat_id", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="engagementsla",
            index=models.Index(
                fields=["company", "actif"],
                name="contrats_sla_co_act",
            ),
        ),
    ]
