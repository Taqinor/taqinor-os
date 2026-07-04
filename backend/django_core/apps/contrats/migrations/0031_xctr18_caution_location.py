# XCTR18 — Caution (dépôt de garantie) sur location : champs additifs sur
# `OrdreLocation` + nouveau modèle `CautionLocationLog` (journal des
# transitions). Additif, aucune donnée existante touchée.

import django.conf
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(django.conf.settings.AUTH_USER_MODEL),
        ("authentication", "0001_initial"),
        ("contrats", "0030_ordrelocation"),
    ]

    operations = [
        migrations.AddField(
            model_name="ordrelocation",
            name="caution_montant",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=12, null=True,
                verbose_name="Montant de la caution"),
        ),
        migrations.AddField(
            model_name="ordrelocation",
            name="caution_statut",
            field=models.CharField(
                choices=[
                    ("aucune", "Aucune"),
                    ("encaissee", "Encaissée"),
                    ("restituee", "Restituée"),
                    ("retenue_partielle", "Retenue partielle"),
                ],
                default="aucune", max_length=20,
                verbose_name="Statut de la caution"),
        ),
        migrations.AddField(
            model_name="ordrelocation",
            name="caution_retenue",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=12, null=True,
                verbose_name="Montant retenu sur la caution"),
        ),
        migrations.AddField(
            model_name="ordrelocation",
            name="caution_motif_retenue",
            field=models.TextField(
                blank=True, default="", verbose_name="Motif de la retenue"),
        ),
        migrations.CreateModel(
            name="CautionLocationLog",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name="ID")),
                ("ancien_statut", models.CharField(
                    blank=True, default="", max_length=20,
                    verbose_name="Ancien statut")),
                ("nouveau_statut", models.CharField(
                    max_length=20, verbose_name="Nouveau statut")),
                ("montant", models.DecimalField(
                    blank=True, decimal_places=2, max_digits=12, null=True,
                    verbose_name="Montant concerné")),
                ("motif", models.TextField(
                    blank=True, default="", verbose_name="Motif")),
                ("date_creation", models.DateTimeField(
                    auto_now_add=True, verbose_name="Créé le")),
                ("auteur", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="caution_location_logs",
                    to=django.conf.settings.AUTH_USER_MODEL,
                    verbose_name="Auteur")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="contrats_caution_location_logs",
                    to="authentication.company", verbose_name="Société")),
                ("ordre_location", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="caution_logs",
                    to="contrats.ordrelocation",
                    verbose_name="Ordre de location")),
            ],
            options={
                "verbose_name": "Journal de caution (location)",
                "verbose_name_plural": "Journaux de caution (location)",
                "ordering": ["-date_creation", "-id"],
            },
        ),
    ]
