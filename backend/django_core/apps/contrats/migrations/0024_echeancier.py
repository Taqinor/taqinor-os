"""Migration additive : modèles ``EcheancierContrat`` et ``LigneEcheance``
(CONTRAT30 — échéancier de paiement : en-tête + lignes).

Entièrement additive (``CreateModel`` + contrainte + index) — réversible via
``DeleteModel``. Un ``EcheancierContrat`` regroupe les échéances de paiement d'un
``Contrat`` ; ses ``LigneEcheance`` (numéro = max+1 par échéancier, posé côté
serveur) portent montant + date. Les statuts de ces objets sont propres au suivi
de l'échéancier/paiement et ne touchent jamais le ``Contrat.statut`` (CONTRAT12)
ni le funnel ``STAGES.py`` (rule #2) ; aucune facture n'est émise (CONTRAT31 est
séparé). La société est posée côté serveur.

RUNTIME-SAFETY (leçon FG136) : ``libelle`` borné (≤200) ; la contrainte
d'unicité ``(echeancier, numero)`` et les index sont nommés explicitement
(≤30 chars).
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contrats", "0023_caution"),
    ]

    operations = [
        migrations.CreateModel(
            name="EcheancierContrat",
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
                    "periodicite",
                    models.CharField(
                        choices=[
                            ("unique", "Paiement unique"),
                            ("mensuelle", "Mensuelle"),
                            ("trimestrielle", "Trimestrielle"),
                            ("semestrielle", "Semestrielle"),
                            ("annuelle", "Annuelle"),
                            ("personnalisee", "Personnalisée"),
                        ],
                        default="unique",
                        max_length=20,
                        verbose_name="Périodicité",
                    ),
                ),
                (
                    "montant_total",
                    models.DecimalField(
                        decimal_places=2,
                        default=0,
                        max_digits=14,
                        verbose_name="Montant total",
                    ),
                ),
                (
                    "devise",
                    models.CharField(
                        default="MAD", max_length=3, verbose_name="Devise"
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("brouillon", "Brouillon"),
                            ("actif", "Actif"),
                            ("solde", "Soldé"),
                            ("annule", "Annulé"),
                        ],
                        default="brouillon",
                        max_length=20,
                        verbose_name="Statut",
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
                        related_name="contrats_echeanciers",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "contrat",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="echeanciers",
                        to="contrats.contrat",
                        verbose_name="Contrat",
                    ),
                ),
            ],
            options={
                "verbose_name": "Échéancier de contrat",
                "verbose_name_plural": "Échéanciers de contrat",
                "ordering": ["contrat_id", "-id"],
            },
        ),
        migrations.CreateModel(
            name="LigneEcheance",
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
                        verbose_name="Numéro d'échéance"
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
                    "date_echeance",
                    models.DateField(verbose_name="Date d'échéance"),
                ),
                (
                    "montant",
                    models.DecimalField(
                        decimal_places=2,
                        default=0,
                        max_digits=14,
                        verbose_name="Montant",
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("a_venir", "À venir"),
                            ("payee", "Payée"),
                            ("en_retard", "En retard"),
                            ("annulee", "Annulée"),
                        ],
                        default="a_venir",
                        max_length=20,
                        verbose_name="Statut",
                    ),
                ),
                (
                    "date_paiement",
                    models.DateField(
                        blank=True, null=True, verbose_name="Payée le"
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
                        related_name="contrats_lignes_echeance",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "echeancier",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lignes",
                        to="contrats.echeanciercontrat",
                        verbose_name="Échéancier",
                    ),
                ),
            ],
            options={
                "verbose_name": "Ligne d'échéance",
                "verbose_name_plural": "Lignes d'échéance",
                "ordering": ["echeancier_id", "numero", "id"],
            },
        ),
        migrations.AddConstraint(
            model_name="ligneecheance",
            constraint=models.UniqueConstraint(
                fields=["echeancier", "numero"],
                name="contrats_ligneech_uniq",
            ),
        ),
        migrations.AddIndex(
            model_name="ligneecheance",
            index=models.Index(
                fields=["company", "statut", "date_echeance"],
                name="contrats_ligneech_co_st",
            ),
        ),
        migrations.AddIndex(
            model_name="echeanciercontrat",
            index=models.Index(
                fields=["company", "statut"],
                name="contrats_ech_co_st",
            ),
        ),
    ]
