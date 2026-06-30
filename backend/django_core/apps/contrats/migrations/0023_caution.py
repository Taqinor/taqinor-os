"""Migration additive : modèle ``Caution``
(CONTRAT29 — registre des cautions/garanties liées).

Entièrement additive (``CreateModel`` + index) — réversible via ``DeleteModel``.
Une ``Caution`` recense une garantie financière liée à un ``Contrat`` (caution de
soumission/bonne exécution/restitution d'acompte/retenue/société mère…), son
garant, son montant et ses dates de validité, avec un statut de registre
(active → mainlevee/appelee/expiree/annulee). Le statut est propre au registre :
il ne touche jamais le ``Contrat.statut`` (CONTRAT12) ni le funnel ``STAGES.py``
(rule #2). La société est posée côté serveur (déduite du contrat).

RUNTIME-SAFETY (leçon FG136) : ``garant`` / ``reference`` bornés, ``note`` en
``TextField`` ; les index sont nommés explicitement (≤30 chars).
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contrats", "0022_retenuegarantie"),
    ]

    operations = [
        migrations.CreateModel(
            name="Caution",
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
                    "type_caution",
                    models.CharField(
                        choices=[
                            ("soumission", "Caution de soumission"),
                            ("bonne_execution", "Caution de bonne exécution"),
                            (
                                "restitution_acompte",
                                "Restitution d'acompte",
                            ),
                            ("retenue_garantie", "Garantie de retenue"),
                            ("societe_mere", "Garantie société mère"),
                            ("autre", "Autre"),
                        ],
                        default="bonne_execution",
                        max_length=30,
                        verbose_name="Type de caution",
                    ),
                ),
                (
                    "garant",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=200,
                        verbose_name="Garant",
                    ),
                ),
                (
                    "reference",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=100,
                        verbose_name="Référence",
                    ),
                ),
                (
                    "montant",
                    models.DecimalField(
                        decimal_places=2,
                        default=0,
                        max_digits=14,
                        verbose_name="Montant garanti",
                    ),
                ),
                (
                    "devise",
                    models.CharField(
                        default="MAD", max_length=3, verbose_name="Devise"
                    ),
                ),
                (
                    "date_emission",
                    models.DateField(
                        blank=True, null=True, verbose_name="Date d'émission"
                    ),
                ),
                (
                    "date_expiration",
                    models.DateField(
                        blank=True,
                        null=True,
                        verbose_name="Date d'expiration",
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("active", "Active"),
                            ("mainlevee", "Mainlevée"),
                            ("appelee", "Appelée"),
                            ("expiree", "Expirée"),
                            ("annulee", "Annulée"),
                        ],
                        default="active",
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
                        related_name="contrats_cautions",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "contrat",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cautions",
                        to="contrats.contrat",
                        verbose_name="Contrat",
                    ),
                ),
            ],
            options={
                "verbose_name": "Caution / garantie",
                "verbose_name_plural": "Cautions / garanties",
                "ordering": ["contrat_id", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="caution",
            index=models.Index(
                fields=["company", "statut"],
                name="contrats_caut_co_st",
            ),
        ),
        migrations.AddIndex(
            model_name="caution",
            index=models.Index(
                fields=["contrat", "date_expiration"],
                name="contrats_caut_ct_exp",
            ),
        ),
    ]
