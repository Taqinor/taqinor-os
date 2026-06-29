"""Migration additive : création du modèle ``ContratActivity``
(CONTRAT15 — chatter / journal du contrat, audit des transitions).

Entièrement additive (``CreateModel`` + index) — réversible via ``DeleteModel``.
Une ``ContratActivity`` est une entrée de chatter à la Odoo d'un ``Contrat`` :
soit une transition AUTOMATIQUE auditée (changement de ``statut`` /
``confidentialite``, pas du workflow d'approbation CONTRAT14), soit une NOTE
manuelle. La société et l'auteur sont posés côté serveur (jamais lus du corps de
requête). Les instantanés ``old_value`` / ``new_value`` sont des ``TextField``
pour ne jamais dépasser une longueur maximale (leçon FG136). L'index est nommé
explicitement (≤30 chars) pour éviter la divergence d'auto-nommage Django.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("contrats", "0011_etapeapprobation"),
    ]

    operations = [
        migrations.CreateModel(
            name="ContratActivity",
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
                    "type",
                    models.CharField(
                        choices=[("log", "Transition"), ("note", "Note")],
                        max_length=10,
                        verbose_name="Type",
                    ),
                ),
                (
                    "field",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=100,
                        verbose_name="Champ",
                    ),
                ),
                (
                    "old_value",
                    models.TextField(
                        blank=True,
                        default="",
                        verbose_name="Ancienne valeur",
                    ),
                ),
                (
                    "new_value",
                    models.TextField(
                        blank=True,
                        default="",
                        verbose_name="Nouvelle valeur",
                    ),
                ),
                (
                    "message",
                    models.TextField(
                        blank=True, default="", verbose_name="Message"
                    ),
                ),
                (
                    "date_creation",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Créé le"
                    ),
                ),
                (
                    "auteur",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="contrats_activites",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Auteur",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="contrats_activites",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "contrat",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="activites",
                        to="contrats.contrat",
                        verbose_name="Contrat",
                    ),
                ),
            ],
            options={
                "verbose_name": "Activité contrat",
                "verbose_name_plural": "Activités contrat",
                "ordering": ["-date_creation", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="contratactivity",
            index=models.Index(
                fields=["contrat", "-date_creation"],
                name="contrats_act_ct_date",
            ),
        ),
    ]
