# ZMFG6 - Feuilles de maintenance (worksheets) remplies par le technicien.
# Additif : gate societe worksheets_maintenance_actifs (defaut OFF) + deux
# nouveaux modeles (modele de feuille + feuille par ticket). Aucun ticket
# existant n'est affecte tant que la societe n'active pas le toggle.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("authentication", "0001_initial"),
        ("sav", "0046_xctr16_facturation_usage"),
    ]

    operations = [
        migrations.AddField(
            model_name="savslasettings",
            name="worksheets_maintenance_actifs",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Active la feuille de maintenance remplie par le "
                    "technicien sur les tickets (parité Odoo « Custom "
                    "Maintenance Worksheets »)."
                ),
                verbose_name="Feuilles de maintenance (worksheets) actives",
            ),
        ),
        migrations.CreateModel(
            name="WorksheetMaintenanceModele",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nom", models.CharField(max_length=150)),
                (
                    "type_ticket_applicable",
                    models.CharField(
                        choices=[
                            ("preventif", "Préventif"),
                            ("correctif", "Correctif"),
                            ("tous", "Tous types"),
                        ],
                        default="tous",
                        max_length=15,
                    ),
                ),
                (
                    "champs",
                    models.JSONField(
                        blank=True,
                        default=list,
                        help_text=(
                            'Liste de champs typés : [{"cle", "libelle", '
                            '"type": texte|nombre|case|mesure, "requis"}].'
                        ),
                    ),
                ),
                ("actif", models.BooleanField(default=True)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                (
                    "company",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="worksheet_maintenance_modeles",
                        to="authentication.company",
                    ),
                ),
            ],
            options={
                "verbose_name": "Modèle de feuille de maintenance",
                "verbose_name_plural": "Modèles de feuille de maintenance",
                "ordering": ["nom"],
            },
        ),
        migrations.CreateModel(
            name="TicketWorksheet",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("valeurs", models.JSONField(blank=True, default=dict)),
                ("complete", models.BooleanField(default=False)),
                ("complete_le", models.DateTimeField(blank=True, null=True)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                (
                    "company",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ticket_worksheets",
                        to="authentication.company",
                    ),
                ),
                (
                    "complete_par",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "modele",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="ticket_worksheets",
                        to="sav.worksheetmaintenancemodele",
                    ),
                ),
                (
                    "ticket",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="worksheet",
                        to="sav.ticket",
                    ),
                ),
            ],
            options={
                "verbose_name": "Feuille de maintenance (ticket)",
                "verbose_name_plural": "Feuilles de maintenance (ticket)",
            },
        ),
    ]
