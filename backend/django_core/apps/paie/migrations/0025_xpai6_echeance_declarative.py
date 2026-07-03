# Generated manually — XPAI6 échéancier déclaratif paie.
#
# Additif : nouveau modèle EcheanceDeclarative (company-scoped), un calendrier
# de conformité (BDS/IR mensuel/9421/CIMR) généré automatiquement à la
# création d'une PeriodePaie. Aucun champ existant modifié.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """XPAI6 — Échéancier déclaratif paie."""

    dependencies = [
        ("paie", "0024_xpai4_gratification_hors_cycle"),
    ]

    operations = [
        migrations.CreateModel(
            name="EcheanceDeclarative",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("type_echeance", models.CharField(
                    choices=[
                        ("bds", "BDS (CNSS)"),
                        ("ir_mensuel", "IR mensuel"),
                        ("etat_9421", "État 9421 (annuel)"),
                        ("cimr", "CIMR"),
                    ],
                    max_length=12, verbose_name="Type")),
                ("date_limite", models.DateField(verbose_name="Date limite")),
                ("statut", models.CharField(
                    choices=[
                        ("a_generer", "À générer"),
                        ("generee", "Générée"),
                        ("deposee", "Déposée"),
                        ("payee", "Payée"),
                    ],
                    default="a_generer", max_length=10,
                    verbose_name="Statut")),
                ("date_notification", models.DateTimeField(
                    blank=True, null=True,
                    verbose_name="Rappel envoyé le")),
                ("date_creation", models.DateTimeField(
                    auto_now_add=True, verbose_name="Créé le")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="paie_echeances_declaratives",
                    to="authentication.company", verbose_name="Société")),
                ("periode", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="echeances_declaratives",
                    to="paie.periodepaie", verbose_name="Période")),
            ],
            options={
                "verbose_name": "Échéance déclarative",
                "verbose_name_plural": "Échéances déclaratives",
                "ordering": ["date_limite", "type_echeance"],
            },
        ),
        migrations.AlterUniqueTogether(
            name="echeancedeclarative",
            unique_together={("periode", "type_echeance")},
        ),
    ]
