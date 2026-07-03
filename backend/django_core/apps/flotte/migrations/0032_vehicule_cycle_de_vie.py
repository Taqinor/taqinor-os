# Generated for XFLT4 — fiche véhicule enrichie + cycle de vie complet. Ajoute
# des champs additifs sur ``Vehicule`` (vin, annee, date_acquisition,
# type_fiscal, tags, checklist_mise_en_service), étend ``Vehicule.Statut`` avec
# commande/a_vendre/vendu (les 3 statuts historiques actif/maintenance/reforme
# restent inchangés), et ajoute le modèle ``JournalStatutVehicule`` (transitions
# de statut journalisées, serveur-side). Additif, multi-société.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("flotte", "0031_coutvehicule"),
    ]

    operations = [
        migrations.AddField(
            model_name="vehicule",
            name="vin",
            field=models.CharField(
                blank=True, max_length=30, verbose_name="N° châssis (VIN)"
            ),
        ),
        migrations.AddField(
            model_name="vehicule",
            name="annee",
            field=models.PositiveSmallIntegerField(
                blank=True, null=True, verbose_name="Année"
            ),
        ),
        migrations.AddField(
            model_name="vehicule",
            name="date_acquisition",
            field=models.DateField(
                blank=True, null=True, verbose_name="Date d'acquisition"
            ),
        ),
        migrations.AddField(
            model_name="vehicule",
            name="type_fiscal",
            field=models.CharField(
                blank=True,
                choices=[
                    ("utilitaire", "Utilitaire"),
                    ("tourisme", "Tourisme"),
                ],
                max_length=15,
                verbose_name="Type fiscal",
            ),
        ),
        migrations.AddField(
            model_name="vehicule",
            name="tags",
            field=models.JSONField(
                blank=True, default=list, verbose_name="Tags"
            ),
        ),
        migrations.AddField(
            model_name="vehicule",
            name="checklist_mise_en_service",
            field=models.JSONField(
                blank=True, default=dict,
                verbose_name="Checklist de mise en service",
            ),
        ),
        migrations.AlterField(
            model_name="vehicule",
            name="statut",
            field=models.CharField(
                choices=[
                    ("actif", "Actif"),
                    ("maintenance", "En maintenance"),
                    ("reforme", "Réformé"),
                    ("commande", "Commandé"),
                    ("a_vendre", "À vendre"),
                    ("vendu", "Vendu"),
                ],
                default="actif",
                max_length=20,
                verbose_name="Statut",
            ),
        ),
        migrations.CreateModel(
            name="JournalStatutVehicule",
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
                    "ancien_statut",
                    models.CharField(
                        blank=True, max_length=20,
                        verbose_name="Ancien statut",
                    ),
                ),
                (
                    "nouveau_statut",
                    models.CharField(
                        max_length=20, verbose_name="Nouveau statut"
                    ),
                ),
                (
                    "horodatage",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Horodatage"
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="flotte_journal_statuts_vehicule",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "vehicule",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="journal_statuts",
                        to="flotte.vehicule",
                        verbose_name="Véhicule",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="flotte_journal_statuts_vehicule",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Utilisateur",
                    ),
                ),
            ],
            options={
                "verbose_name": "Journal de statut véhicule",
                "verbose_name_plural": "Journal des statuts véhicule",
                "ordering": ["-horodatage", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="journalstatutvehicule",
            index=models.Index(
                fields=["company", "vehicule"],
                name="flotte_jsv_co_veh_idx",
            ),
        ),
    ]
