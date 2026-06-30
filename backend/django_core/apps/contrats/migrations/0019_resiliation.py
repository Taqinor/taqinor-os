"""Migration additive : création du modèle ``Resiliation``
(CONTRAT25 — résiliation d'un contrat : motif / préavis / solde).

Entièrement additive (``CreateModel`` + contrainte d'unicité partielle + index) —
réversible via ``DeleteModel``. Une ``Resiliation`` enregistre la résiliation
d'un ``Contrat`` (motif, date d'effet, préavis observé, solde de tout compte) et
sa création (via ``services.resilier_contrat``) fait basculer le
``Contrat.statut`` vers ``resilie`` par la machine d'états GARDÉE
(``machine_etats.changer_statut``) — jamais une écriture directe du statut,
jamais un funnel ``STAGES.py`` (rule #2). Elle peut figer un instantané immuable
(``VersionContrat`` — CONTRAT18) qu'elle référence (``version_creee``,
``SET_NULL``). La société/l'auteur/la date de demande/le statut sont posés côté
serveur (jamais lus du corps de requête).

RUNTIME-SAFETY (leçon FG136) : ``motif`` est un ``TextField`` (un motif peut être
long) et ``solde`` un ``DecimalField`` nullable. La contrainte d'unicité
PARTIELLE « une seule résiliation active par contrat » (``statut != annulee``) et
l'index sont nommés explicitement (≤30 chars) pour éviter la divergence
d'auto-nommage Django.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("contrats", "0018_avenant"),
    ]

    operations = [
        migrations.CreateModel(
            name="Resiliation",
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
                    "motif",
                    models.TextField(
                        blank=True,
                        default="",
                        verbose_name="Motif de la résiliation",
                    ),
                ),
                (
                    "date_demande",
                    models.DateField(
                        blank=True, null=True, verbose_name="Date de demande"
                    ),
                ),
                (
                    "date_effet",
                    models.DateField(
                        blank=True, null=True, verbose_name="Date d'effet"
                    ),
                ),
                (
                    "preavis_jours",
                    models.PositiveIntegerField(
                        blank=True, null=True, verbose_name="Préavis (jours)"
                    ),
                ),
                (
                    "solde",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=14,
                        null=True,
                        verbose_name="Solde / règlement",
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("demande", "Demandée"),
                            ("effective", "Effective"),
                            ("annulee", "Annulée"),
                        ],
                        default="demande",
                        max_length=20,
                        verbose_name="Statut",
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
                        related_name="contrats_resiliations",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "contrat",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="resiliations",
                        to="contrats.contrat",
                        verbose_name="Contrat",
                    ),
                ),
                (
                    "version_creee",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="resiliation",
                        to="contrats.versioncontrat",
                        verbose_name="Version figée",
                    ),
                ),
                (
                    "cree_par",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="contrats_resiliations_creees",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Créée par",
                    ),
                ),
            ],
            options={
                "verbose_name": "Résiliation de contrat",
                "verbose_name_plural": "Résiliations de contrat",
                "ordering": ["contrat_id", "-id"],
            },
        ),
        migrations.AddConstraint(
            model_name="resiliation",
            constraint=models.UniqueConstraint(
                condition=models.Q(("statut", "annulee"), _negated=True),
                fields=["contrat"],
                name="contrats_resil_active_uniq",
            ),
        ),
        migrations.AddIndex(
            model_name="resiliation",
            index=models.Index(
                fields=["contrat", "statut"],
                name="contrats_resil_ct_st",
            ),
        ),
    ]
