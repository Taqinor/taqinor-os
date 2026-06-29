"""Migration additive : création du modèle ``VersionContrat``
(CONTRAT18 — versionnage IMMUABLE des rendus de contrat).

Entièrement additive (``CreateModel`` + contrainte d'unicité + index) —
réversible via ``DeleteModel``. Une ``VersionContrat`` fige un instantané
immuable du contenu d'un contrat (corps fusionné — CONTRAT10) et,
éventuellement, la clé d'un rendu PDF stocké (MinIO), de sorte que les états
antérieurs sont préservés même quand le contrat évolue. Le numéro de version est
posé côté serveur (``max(version)+1`` sous verrou de ligne — jamais ``count()+1``)
et la société/l'auteur sont posés côté serveur (jamais lus du corps de requête).

RUNTIME-SAFETY (leçon FG136) : ``contenu`` est un ``TextField`` (un rendu peut
être très long) ; ``motif`` ≤255 et ``fichier_key`` ≤512 (clé d'objet MinIO). La
contrainte d'unicité ``(contrat, version)`` et l'index sont nommés explicitement
(≤30 chars) pour éviter la divergence d'auto-nommage Django.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("contrats", "0013_signaturecontrat"),
    ]

    operations = [
        migrations.CreateModel(
            name="VersionContrat",
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
                    "version",
                    models.PositiveIntegerField(verbose_name="Version"),
                ),
                (
                    "contenu",
                    models.TextField(
                        blank=True, default="", verbose_name="Contenu figé"
                    ),
                ),
                (
                    "fichier_key",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=512,
                        verbose_name="Clé du rendu PDF",
                    ),
                ),
                (
                    "motif",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=255,
                        verbose_name="Motif",
                    ),
                ),
                (
                    "cree_le",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Créée le"
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="contrats_versions",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "contrat",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="versions",
                        to="contrats.contrat",
                        verbose_name="Contrat",
                    ),
                ),
                (
                    "cree_par",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="contrats_versions_creees",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Créée par",
                    ),
                ),
            ],
            options={
                "verbose_name": "Version de contrat",
                "verbose_name_plural": "Versions de contrat",
                "ordering": ["contrat_id", "-version", "-id"],
            },
        ),
        migrations.AddConstraint(
            model_name="versioncontrat",
            constraint=models.UniqueConstraint(
                fields=["contrat", "version"],
                name="contrats_version_uniq",
            ),
        ),
        migrations.AddIndex(
            model_name="versioncontrat",
            index=models.Index(
                fields=["contrat", "-version"],
                name="contrats_ver_ct_ver",
            ),
        ),
    ]
