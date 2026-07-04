# XRH19 — Emails candidats automatiques par étape.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("rh", "0055_candidature_activity"),
    ]

    operations = [
        migrations.AddField(
            model_name="candidature",
            name="emails_auto",
            field=models.BooleanField(default=True),
        ),
        migrations.CreateModel(
            name="GabaritEmailRecrutement",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name="ID")),
                ("etape", models.CharField(
                    choices=[
                        ("recu", "Reçu"), ("preselection", "Présélection"),
                        ("entretien", "Entretien"), ("offre", "Offre"),
                        ("embauche", "Embauché"), ("rejete", "Rejeté")],
                    max_length=20)),
                ("objet", models.CharField(max_length=255)),
                ("corps", models.TextField()),
                ("actif", models.BooleanField(default=True)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="rh_gabarits_email_recrutement",
                    to="authentication.company")),
            ],
            options={
                "verbose_name": "Gabarit email recrutement",
                "verbose_name_plural": "Gabarits email recrutement",
                "ordering": ["etape"],
            },
        ),
        migrations.AddIndex(
            model_name="gabaritemailrecrutement",
            index=models.Index(
                fields=["company", "etape", "actif"],
                name="rh_gabarit_email_etape_idx"),
        ),
    ]
