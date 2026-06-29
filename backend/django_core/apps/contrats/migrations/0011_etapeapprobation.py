"""Migration additive : création du modèle ``EtapeApprobation``
(CONTRAT14 — étapes & workflow d'approbation interne d'un contrat).

Entièrement additive (``CreateModel`` + index) — réversible via ``DeleteModel``.
Une ``EtapeApprobation`` matérialise une décision d'approbation interne d'un
``Contrat`` (statut LOCAL ``en_attente`` → ``approuve`` / ``rejete``), instanciée
à partir de la ``RegleApprobation`` la plus spécifique (CONTRAT13). Les statuts
sont propres au workflow et n'ont aucun lien avec ``STAGES.py`` ni avec le
``Contrat.statut``. Les index sont nommés explicitement (≤30 chars) pour éviter
la divergence d'auto-nommage Django.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0008_customuser_avatar_key_customuser_poste"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("contrats", "0010_regleapprobation"),
    ]

    operations = [
        migrations.CreateModel(
            name="EtapeApprobation",
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
                    "niveau",
                    models.PositiveIntegerField(
                        default=1,
                        verbose_name="Niveau / rang de l'étape",
                    ),
                ),
                (
                    "niveau_approbation",
                    models.CharField(
                        choices=[
                            ("responsable", "Responsable"),
                            ("administrateur", "Administrateur"),
                            ("direction", "Direction"),
                        ],
                        default="responsable",
                        max_length=20,
                        verbose_name="Niveau d'approbation requis",
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("en_attente", "En attente"),
                            ("approuve", "Approuvé"),
                            ("rejete", "Rejeté"),
                        ],
                        default="en_attente",
                        max_length=20,
                        verbose_name="Statut",
                    ),
                ),
                (
                    "decision_le",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="Décidé le"
                    ),
                ),
                (
                    "commentaire",
                    models.TextField(
                        blank=True, default="", verbose_name="Commentaire"
                    ),
                ),
                (
                    "date_creation",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Créé le"
                    ),
                ),
                (
                    "approbateur",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="contrats_etapes_approuvees",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Approbateur",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="contrats_etapes_approbation",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "contrat",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="etapes_approbation",
                        to="contrats.contrat",
                        verbose_name="Contrat",
                    ),
                ),
                (
                    "regle",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="etapes_approbation",
                        to="contrats.regleapprobation",
                        verbose_name="Règle d'approbation source",
                    ),
                ),
            ],
            options={
                "verbose_name": "Étape d'approbation",
                "verbose_name_plural": "Étapes d'approbation",
                "ordering": ["contrat_id", "niveau", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="etapeapprobation",
            index=models.Index(
                fields=["company", "statut"],
                name="contrats_etapeapp_co_sta",
            ),
        ),
        migrations.AddIndex(
            model_name="etapeapprobation",
            index=models.Index(
                fields=["contrat", "niveau"],
                name="contrats_etapeapp_ct_niv",
            ),
        ),
    ]
