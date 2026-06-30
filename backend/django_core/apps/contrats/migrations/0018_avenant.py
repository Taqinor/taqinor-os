"""Migration additive : création du modèle ``Avenant``
(CONTRAT24 — amendement de contrat → nouvelle version immuable).

Entièrement additive (``CreateModel`` + contrainte d'unicité + index) —
réversible via ``DeleteModel``. Un ``Avenant`` enregistre une modification
apportée à un ``Contrat`` et produit en aval un instantané immuable
(``VersionContrat`` — CONTRAT18) figeant l'état amendé ; il pointe vers cette
version (``version_creee``, ``SET_NULL``). Le numéro d'avenant est posé côté
serveur (``max(numero)+1`` sous verrou de ligne — jamais ``count()+1``) et la
société/l'auteur sont posés côté serveur (jamais lus du corps de requête).

RUNTIME-SAFETY (leçon FG136) : ``objet`` ≤255 (CharField borné), ``description``
est un ``TextField`` (un descriptif peut être long) et ``montant_delta`` est un
``DecimalField`` nullable. La contrainte d'unicité ``(contrat, numero)`` et
l'index sont nommés explicitement (≤30 chars) pour éviter la divergence
d'auto-nommage Django.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("contrats", "0017_contrat_renouvellement"),
    ]

    operations = [
        migrations.CreateModel(
            name="Avenant",
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
                        verbose_name="Numéro d'avenant"
                    ),
                ),
                (
                    "objet",
                    models.CharField(
                        max_length=255, verbose_name="Objet de l'avenant"
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        blank=True, default="", verbose_name="Description"
                    ),
                ),
                (
                    "date_effet",
                    models.DateField(
                        blank=True, null=True, verbose_name="Date d'effet"
                    ),
                ),
                (
                    "montant_delta",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=14,
                        null=True,
                        verbose_name="Variation de montant",
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
                        related_name="contrats_avenants",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "contrat",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="avenants",
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
                        related_name="avenant",
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
                        related_name="contrats_avenants_crees",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Créé par",
                    ),
                ),
            ],
            options={
                "verbose_name": "Avenant de contrat",
                "verbose_name_plural": "Avenants de contrat",
                "ordering": ["contrat_id", "-numero", "-id"],
            },
        ),
        migrations.AddConstraint(
            model_name="avenant",
            constraint=models.UniqueConstraint(
                fields=["contrat", "numero"],
                name="contrats_avenant_uniq",
            ),
        ),
        migrations.AddIndex(
            model_name="avenant",
            index=models.Index(
                fields=["contrat", "-numero"],
                name="contrats_aven_ct_num",
            ),
        ),
    ]
