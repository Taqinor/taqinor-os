"""Migration additive : modèle ``RetenueGarantie``
(CONTRAT28 — retenue de garantie + suivi de libération).

Entièrement additive (``CreateModel`` + index) — réversible via ``DeleteModel``.
Une ``RetenueGarantie`` enregistre la retenue de garantie d'un ``Contrat``
(``montant_base`` × ``taux`` % → ``montant_retenu`` posé côté serveur) et son
suivi de libération (``statut`` retenue → liberee/annulee + dates clés). Le
``statut`` est propre au suivi de la retenue : il ne touche jamais le
``Contrat.statut`` (CONTRAT12) ni le funnel ``STAGES.py`` (rule #2), et la
libération n'émet aucune facture/aucun mouvement comptable. La société est posée
côté serveur (déduite du contrat).

RUNTIME-SAFETY (leçon FG136) : ``note`` est un ``TextField`` ; les index sont
nommés explicitement (≤30 chars).
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contrats", "0021_engagementsla"),
    ]

    operations = [
        migrations.CreateModel(
            name="RetenueGarantie",
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
                    "montant_base",
                    models.DecimalField(
                        decimal_places=2,
                        default=0,
                        max_digits=14,
                        verbose_name="Montant de base",
                    ),
                ),
                (
                    "taux",
                    models.DecimalField(
                        decimal_places=2,
                        default=0,
                        max_digits=6,
                        verbose_name="Taux de retenue (%)",
                    ),
                ),
                (
                    "montant_retenu",
                    models.DecimalField(
                        decimal_places=2,
                        default=0,
                        max_digits=14,
                        verbose_name="Montant retenu",
                    ),
                ),
                (
                    "date_retenue",
                    models.DateField(
                        blank=True, null=True, verbose_name="Date de retenue"
                    ),
                ),
                (
                    "date_liberation_prevue",
                    models.DateField(
                        blank=True,
                        null=True,
                        verbose_name="Libération prévue le",
                    ),
                ),
                (
                    "date_liberation_effective",
                    models.DateField(
                        blank=True, null=True, verbose_name="Libérée le"
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("retenue", "Retenue"),
                            ("liberee", "Libérée"),
                            ("annulee", "Annulée"),
                        ],
                        default="retenue",
                        max_length=20,
                        verbose_name="Statut",
                    ),
                ),
                (
                    "note",
                    models.TextField(
                        blank=True, default="", verbose_name="Note"
                    ),
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
                        related_name="contrats_retenues",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "contrat",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="retenues_garantie",
                        to="contrats.contrat",
                        verbose_name="Contrat",
                    ),
                ),
            ],
            options={
                "verbose_name": "Retenue de garantie",
                "verbose_name_plural": "Retenues de garantie",
                "ordering": ["contrat_id", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="retenuegarantie",
            index=models.Index(
                fields=["company", "statut"],
                name="contrats_retg_co_st",
            ),
        ),
        migrations.AddIndex(
            model_name="retenuegarantie",
            index=models.Index(
                fields=["contrat", "date_liberation_prevue"],
                name="contrats_retg_ct_dt",
            ),
        ),
    ]
