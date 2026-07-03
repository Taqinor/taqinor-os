# Generated for XFLT13 — Inspections périodiques paramétrables (check-lists
# DVIR). Crée ``ModeleInspection`` et ``InspectionVehicule``. Additif,
# multi-société.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("flotte", "0037_modelevehicule"),
    ]

    operations = [
        migrations.CreateModel(
            name="ModeleInspection",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("nom", models.CharField(max_length=120, verbose_name="Nom")),
                ("type_actif_cible", models.CharField(
                    choices=[
                        ("vehicule", "Véhicule"), ("engin", "Engin roulant"),
                        ("tous", "Tous"),
                    ], default="tous", max_length=10,
                    verbose_name="Type d'actif visé")),
                ("items", models.JSONField(
                    blank=True, default=list,
                    help_text='[{"libelle": str, "photo_requise": bool, '
                    '"bloquant": bool}, …]',
                    verbose_name="Items de la check-list")),
                ("actif", models.BooleanField(
                    default=True, verbose_name="Actif")),
                ("date_creation", models.DateTimeField(
                    auto_now_add=True, verbose_name="Créé le")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="flotte_modeles_inspection",
                    to="authentication.company", verbose_name="Société")),
            ],
            options={
                "verbose_name": "Modèle d'inspection",
                "verbose_name_plural": "Modèles d'inspection",
                "ordering": ["nom"],
            },
        ),
        migrations.CreateModel(
            name="InspectionVehicule",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("date_inspection", models.DateTimeField(
                    auto_now_add=True, verbose_name="Date de l'inspection")),
                ("resultats", models.JSONField(
                    blank=True, default=list,
                    help_text='[{"libelle": str, "resultat": "pass"|"fail", '
                    '"photo": url|None}, …]',
                    verbose_name="Résultats par item")),
                ("signature_nom", models.CharField(
                    blank=True, max_length=150,
                    verbose_name="Nom du signataire (e-signature)")),
                ("signature_horodatage", models.DateTimeField(
                    blank=True, null=True,
                    verbose_name="Horodatage de signature")),
                ("actif_flotte", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="flotte_inspections_vehicule",
                    to="flotte.actifflotte",
                    verbose_name="Actif (véhicule ou engin)")),
                ("auteur", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="flotte_inspections_vehicule",
                    to=settings.AUTH_USER_MODEL, verbose_name="Auteur")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="flotte_inspections_vehicule",
                    to="authentication.company", verbose_name="Société")),
                ("conducteur", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="flotte_inspections_vehicule",
                    to="flotte.conducteur", verbose_name="Conducteur")),
                ("modele_inspection", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="inspections", to="flotte.modeleinspection",
                    verbose_name="Modèle d'inspection")),
            ],
            options={
                "verbose_name": "Inspection véhicule",
                "verbose_name_plural": "Inspections véhicule",
                "ordering": ["-date_inspection", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="inspectionvehicule",
            index=models.Index(
                fields=["company", "actif_flotte"],
                name="flotte_insp_co_actif_idx"),
        ),
        migrations.AddIndex(
            model_name="inspectionvehicule",
            index=models.Index(
                fields=["company", "conducteur"],
                name="flotte_insp_co_cond_idx"),
        ),
    ]
