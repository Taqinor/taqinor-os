# QK1 — Lead qualification fields captured by the public website (all
# additive + nullable, reversible via the automatic AddField reverse).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0033_client_langue_document"),
    ]

    operations = [
        migrations.AddField(
            model_name="lead",
            name="distributeur",
            field=models.CharField(
                blank=True,
                choices=[
                    ("onee", "ONEE"),
                    ("lydec", "Lydec"),
                    ("redal", "Redal"),
                    ("autre", "Autre"),
                ],
                max_length=12,
                null=True,
                verbose_name="Distributeur d'électricité",
            ),
        ),
        migrations.AddField(
            model_name="lead",
            name="roof_age",
            field=models.PositiveSmallIntegerField(
                blank=True, null=True, verbose_name="Âge de la toiture (ans)"
            ),
        ),
        migrations.AddField(
            model_name="lead",
            name="ownership",
            field=models.CharField(
                blank=True,
                choices=[
                    ("proprietaire", "Propriétaire"),
                    ("locataire", "Locataire"),
                    ("autre", "Autre"),
                ],
                max_length=12,
                null=True,
                verbose_name="Statut d'occupation",
            ),
        ),
        migrations.AddField(
            model_name="lead",
            name="project_timeline",
            field=models.CharField(
                blank=True,
                choices=[
                    ("immediat", "Dès que possible"),
                    ("3_mois", "Moins de 3 mois"),
                    ("6_mois", "3 à 6 mois"),
                    ("plus_tard", "Plus tard / je me renseigne"),
                ],
                max_length=12,
                null=True,
                verbose_name="Horizon du projet",
            ),
        ),
        migrations.AddField(
            model_name="lead",
            name="financing_intent",
            field=models.CharField(
                blank=True,
                choices=[
                    ("cash", "Comptant"),
                    ("credit", "Crédit / financement"),
                    ("indecis", "Pas encore décidé"),
                ],
                max_length=12,
                null=True,
                verbose_name="Financement envisagé",
            ),
        ),
        migrations.AddField(
            model_name="lead",
            name="futures_charges",
            field=models.JSONField(
                blank=True,
                help_text="Liste parmi 'clim', 've', 'pompe'.",
                null=True,
                verbose_name="Charges futures prévues",
            ),
        ),
    ]
