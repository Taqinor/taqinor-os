"""Migration additive : modèles ``JalonContrat`` et ``Obligation``
(CONTRAT26 — livrables & jalons).

Entièrement additive (``CreateModel`` + contraintes + index) — réversible via
``DeleteModel``. Un ``JalonContrat`` matérialise une étape clé datée d'un
``Contrat`` (numéro = max+1 par contrat, posé côté serveur) ; une ``Obligation``
recense un livrable/engagement rattaché au contrat (et éventuellement à un
jalon). Les statuts de ces objets sont PROPRES au suivi des obligations/jalons
et ne touchent JAMAIS le ``Contrat.statut`` (CONTRAT12) ni le funnel
``STAGES.py`` (rule #2). La société est posée côté serveur (déduite du contrat).

RUNTIME-SAFETY (leçon FG136) : ``intitule`` est borné (≤255) et ``description``
un ``TextField``. La contrainte d'unicité ``(contrat, numero)`` du jalon et les
index sont nommés explicitement (≤30 chars) pour éviter la divergence
d'auto-nommage Django.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contrats", "0019_resiliation"),
    ]

    operations = [
        migrations.CreateModel(
            name="JalonContrat",
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
                    "numero",
                    models.PositiveIntegerField(
                        verbose_name="Numéro de jalon"
                    ),
                ),
                (
                    "intitule",
                    models.CharField(max_length=255, verbose_name="Intitulé"),
                ),
                (
                    "description",
                    models.TextField(
                        blank=True, default="", verbose_name="Description"
                    ),
                ),
                (
                    "date_cible",
                    models.DateField(
                        blank=True, null=True, verbose_name="Date cible"
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("a_venir", "À venir"),
                            ("en_cours", "En cours"),
                            ("atteint", "Atteint"),
                            ("en_retard", "En retard"),
                            ("annule", "Annulé"),
                        ],
                        default="a_venir",
                        max_length=20,
                        verbose_name="Statut",
                    ),
                ),
                (
                    "date_atteinte",
                    models.DateField(
                        blank=True, null=True, verbose_name="Atteint le"
                    ),
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
                        related_name="contrats_jalons",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "contrat",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="jalons",
                        to="contrats.contrat",
                        verbose_name="Contrat",
                    ),
                ),
            ],
            options={
                "verbose_name": "Jalon de contrat",
                "verbose_name_plural": "Jalons de contrat",
                "ordering": ["contrat_id", "numero", "id"],
            },
        ),
        migrations.CreateModel(
            name="Obligation",
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
                    "intitule",
                    models.CharField(max_length=255, verbose_name="Intitulé"),
                ),
                (
                    "description",
                    models.TextField(
                        blank=True, default="", verbose_name="Description"
                    ),
                ),
                (
                    "redevable",
                    models.CharField(
                        choices=[
                            ("prestataire", "Prestataire"),
                            ("client", "Client"),
                            ("autre", "Autre"),
                        ],
                        default="prestataire",
                        max_length=20,
                        verbose_name="Partie redevable",
                    ),
                ),
                (
                    "date_echeance",
                    models.DateField(
                        blank=True, null=True, verbose_name="Date d'échéance"
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("a_faire", "À faire"),
                            ("en_cours", "En cours"),
                            ("faite", "Réalisée"),
                            ("en_retard", "En retard"),
                            ("annulee", "Annulée"),
                        ],
                        default="a_faire",
                        max_length=20,
                        verbose_name="Statut",
                    ),
                ),
                (
                    "date_realisation",
                    models.DateField(
                        blank=True, null=True, verbose_name="Réalisée le"
                    ),
                ),
                (
                    "ordre",
                    models.PositiveIntegerField(
                        default=0, verbose_name="Ordre"
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
                        related_name="contrats_obligations",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "contrat",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="obligations",
                        to="contrats.contrat",
                        verbose_name="Contrat",
                    ),
                ),
                (
                    "jalon",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="obligations",
                        to="contrats.jaloncontrat",
                        verbose_name="Jalon",
                    ),
                ),
            ],
            options={
                "verbose_name": "Obligation contractuelle",
                "verbose_name_plural": "Obligations contractuelles",
                "ordering": ["contrat_id", "ordre", "date_echeance", "id"],
            },
        ),
        migrations.AddConstraint(
            model_name="jaloncontrat",
            constraint=models.UniqueConstraint(
                fields=["contrat", "numero"],
                name="contrats_jalon_uniq",
            ),
        ),
        migrations.AddIndex(
            model_name="jaloncontrat",
            index=models.Index(
                fields=["contrat", "date_cible"],
                name="contrats_jalon_ct_dt",
            ),
        ),
        migrations.AddIndex(
            model_name="obligation",
            index=models.Index(
                fields=["company", "statut"],
                name="contrats_oblig_co_st",
            ),
        ),
        migrations.AddIndex(
            model_name="obligation",
            index=models.Index(
                fields=["contrat", "date_echeance"],
                name="contrats_oblig_ct_dt",
            ),
        ),
    ]
