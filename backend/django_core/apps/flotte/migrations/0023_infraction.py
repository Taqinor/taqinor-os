# Generated for FLOTTE26 — infractions / PV de circulation. Ajoute le modèle
# ``Infraction`` : actif lié, conducteur responsable (Conducteur, FLOTTE7, même
# app, facultatif), date, type (excès de vitesse / stationnement / feu rouge /
# document / autre), lieu, référence du PV, montant de l'amende, PV scanné,
# statut (à payer / payée / contestée / classée), date de paiement. Additif,
# multi-société.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0013_customuser_poste_ref"),
        ("flotte", "0022_sinistre"),
    ]

    operations = [
        migrations.CreateModel(
            name="Infraction",
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
                    "date_infraction",
                    models.DateField(verbose_name="Date de l'infraction"),
                ),
                (
                    "type_infraction",
                    models.CharField(
                        choices=[
                            ("exces_vitesse", "Excès de vitesse"),
                            ("stationnement", "Stationnement"),
                            ("feu_rouge", "Feu rouge"),
                            ("document", "Défaut de document"),
                            ("autre", "Autre"),
                        ],
                        default="exces_vitesse",
                        max_length=13,
                        verbose_name="Type d'infraction",
                    ),
                ),
                (
                    "lieu",
                    models.CharField(
                        blank=True, max_length=255, verbose_name="Lieu"
                    ),
                ),
                (
                    "reference_pv",
                    models.CharField(
                        blank=True,
                        max_length=80,
                        verbose_name="Référence du PV",
                    ),
                ),
                (
                    "montant_amende",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=12,
                        null=True,
                        verbose_name="Montant de l'amende (MAD)",
                    ),
                ),
                (
                    "pv_fichier",
                    models.FileField(
                        blank=True,
                        null=True,
                        upload_to="flotte/infractions/pv/%Y/%m/",
                        verbose_name="PV scanné",
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("a_payer", "À payer"),
                            ("payee", "Payée"),
                            ("contestee", "Contestée"),
                            ("classee", "Classée"),
                        ],
                        default="a_payer",
                        max_length=9,
                        verbose_name="Statut",
                    ),
                ),
                (
                    "date_paiement",
                    models.DateField(
                        blank=True,
                        null=True,
                        verbose_name="Date de paiement",
                    ),
                ),
                ("notes", models.TextField(blank=True, verbose_name="Notes")),
                (
                    "date_creation",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Créé le"
                    ),
                ),
                (
                    "actif_flotte",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="flotte_infractions",
                        to="flotte.actifflotte",
                        verbose_name="Actif (véhicule ou engin)",
                    ),
                ),
                (
                    "conducteur",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="flotte_infractions",
                        to="flotte.conducteur",
                        verbose_name="Conducteur responsable",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="flotte_infractions",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
            ],
            options={
                "verbose_name": "Infraction / PV",
                "verbose_name_plural": "Infractions / PV",
                "ordering": ["-date_infraction", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="infraction",
            index=models.Index(
                fields=["company", "statut"],
                name="flotte_inf_co_stat_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="infraction",
            index=models.Index(
                fields=["company", "actif_flotte"],
                name="flotte_inf_co_actif_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="infraction",
            index=models.Index(
                fields=["company", "type_infraction"],
                name="flotte_inf_co_type_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="infraction",
            index=models.Index(
                fields=["company", "date_infraction"],
                name="flotte_inf_co_date_idx",
            ),
        ),
    ]
