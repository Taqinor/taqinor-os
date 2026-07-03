# Generated for XFLT1 — contrats véhicule (leasing/LLD/location/entretien).
# Ajoute le modèle ``ContratVehicule`` : type de contrat, fournisseur/bailleur,
# garage optionnel, dates début/fin, montant récurrent + périodicité, services
# inclus (JSON), km contractuel/an, statut. company posée côté serveur. Additif,
# multi-société. Intégré dans le moteur d'alertes d'échéances (FLOTTE24) comme
# 6e source (``contrat_vehicule``) — voir ``selectors.alertes_echeances_reglementaires``.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("flotte", "0028_demandevehicule"),
    ]

    operations = [
        migrations.CreateModel(
            name="ContratVehicule",
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
                    "type_contrat",
                    models.CharField(
                        choices=[
                            ("leasing", "Leasing"),
                            ("lld", "Location longue durée (LLD)"),
                            ("location", "Location"),
                            ("contrat_entretien", "Contrat d'entretien"),
                            ("garantie_constructeur",
                             "Garantie constructeur"),
                        ],
                        default="location",
                        max_length=25,
                        verbose_name="Type de contrat",
                    ),
                ),
                (
                    "fournisseur",
                    models.CharField(
                        blank=True, max_length=150,
                        verbose_name="Fournisseur / bailleur",
                    ),
                ),
                (
                    "date_debut",
                    models.DateField(verbose_name="Début du contrat"),
                ),
                (
                    "date_fin",
                    models.DateField(
                        blank=True, null=True,
                        verbose_name="Fin du contrat",
                    ),
                ),
                (
                    "montant_recurrent",
                    models.DecimalField(
                        decimal_places=2, default=0, max_digits=12,
                        verbose_name="Montant récurrent (MAD)",
                    ),
                ),
                (
                    "periodicite",
                    models.CharField(
                        choices=[
                            ("mensuel", "Mensuel"),
                            ("trimestriel", "Trimestriel"),
                            ("annuel", "Annuel"),
                        ],
                        default="mensuel",
                        max_length=12,
                        verbose_name="Périodicité",
                    ),
                ),
                (
                    "services_inclus",
                    models.JSONField(
                        blank=True, default=list,
                        verbose_name="Services inclus",
                    ),
                ),
                (
                    "km_contractuel_an",
                    models.PositiveIntegerField(
                        blank=True, null=True,
                        verbose_name="Km contractuel / an",
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("actif", "Actif"),
                            ("expire", "Expiré"),
                        ],
                        default="actif",
                        max_length=7,
                        verbose_name="Statut",
                    ),
                ),
                (
                    "notes",
                    models.TextField(blank=True, verbose_name="Notes"),
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
                        related_name="flotte_contrats_vehicule",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "garage",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="contrats_vehicule",
                        to="flotte.garage",
                        verbose_name="Garage / atelier (si prestataire référencé)",
                    ),
                ),
                (
                    "vehicule",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="contrats_vehicule",
                        to="flotte.vehicule",
                        verbose_name="Véhicule",
                    ),
                ),
            ],
            options={
                "verbose_name": "Contrat véhicule",
                "verbose_name_plural": "Contrats véhicule",
                "ordering": ["date_fin", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="contratvehicule",
            index=models.Index(
                fields=["company", "statut"],
                name="flotte_ctrv_co_stat_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="contratvehicule",
            index=models.Index(
                fields=["company", "vehicule"],
                name="flotte_ctrv_co_veh_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="contratvehicule",
            index=models.Index(
                fields=["company", "date_fin"],
                name="flotte_ctrv_co_fin_idx",
            ),
        ),
    ]
