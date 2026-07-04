# XRH9 — Guichet de demandes RH self-service (attestations à la demande).

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("records", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("rh", "0045_dossieremploye_custom_data"),
    ]

    operations = [
        migrations.CreateModel(
            name="DemandeRH",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name="ID")),
                ("type", models.CharField(
                    choices=[
                        ("attestation_travail", "Attestation de travail"),
                        ("attestation_salaire", "Attestation de salaire"),
                        ("attestation_domiciliation",
                         "Attestation de domiciliation"),
                        ("autre", "Autre"),
                    ],
                    default="attestation_travail", max_length=30)),
                ("message", models.TextField(blank=True, default="")),
                ("statut", models.CharField(
                    choices=[
                        ("soumise", "Soumise"),
                        ("traitee", "Traitée"),
                        ("refusee", "Refusée"),
                    ],
                    default="soumise", max_length=10)),
                ("motif_refus", models.CharField(
                    blank=True, default="", max_length=255)),
                ("traite_le", models.DateTimeField(blank=True, null=True)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("date_modification", models.DateTimeField(auto_now=True)),
                ("attachment", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="rh_demandes", to="records.attachment")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="rh_demandes", to="authentication.company")),
                ("employe", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="demandes_rh", to="rh.dossieremploye")),
                ("traite_par", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="rh_demandes_traitees",
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Demande RH",
                "verbose_name_plural": "Demandes RH",
                "ordering": ["-date_creation"],
            },
        ),
        migrations.AddIndex(
            model_name="demanderh",
            index=models.Index(
                fields=["company", "employe"],
                name="rh_demande_comp_emp_idx"),
        ),
        migrations.AddIndex(
            model_name="demanderh",
            index=models.Index(
                fields=["company", "statut"],
                name="rh_demande_comp_stat_idx"),
        ),
    ]
