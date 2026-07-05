# Generated for XPLT23 — CNDP processing registry + DSR rectification kind.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0010_customuser_supervisor"),
        ("core", "0017_xplt10_dashboard_partage"),
    ]

    operations = [
        migrations.CreateModel(
            name="RegistreTraitement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(help_text="Clé stable du traitement (seed idempotent).", max_length=80, verbose_name="Code")),
                ("finalite", models.CharField(help_text="Finalité du traitement (ex. « gestion des prospects »).", max_length=255, verbose_name="Finalité")),
                ("base_legale", models.CharField(blank=True, default="", help_text="Consentement, contrat, obligation légale, intérêt légitime…", max_length=255, verbose_name="Base légale")),
                ("categories_donnees", models.TextField(blank=True, default="", help_text="Identité, contact, données de facturation, données RH…", verbose_name="Catégories de données")),
                ("categories_personnes", models.TextField(blank=True, default="", help_text="Prospects, clients, salariés, candidats…", verbose_name="Catégories de personnes")),
                ("destinataires", models.TextField(blank=True, default="", help_text="Services internes et sous-traitants destinataires.", verbose_name="Destinataires")),
                ("duree_conservation", models.CharField(blank=True, default="", help_text="Durée légale/contractuelle de conservation.", max_length=255, verbose_name="Durée de conservation")),
                ("numero_recepisse", models.CharField(blank=True, default="", max_length=120, verbose_name="N° de récépissé CNDP")),
                ("date_recepisse", models.DateField(blank=True, null=True, verbose_name="Date de récépissé CNDP")),
                ("actif", models.BooleanField(default=True, verbose_name="Actif")),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="registres_traitement", to="authentication.company", verbose_name="Société")),
            ],
            options={
                "verbose_name": "Traitement CNDP",
                "verbose_name_plural": "Registre des traitements (CNDP)",
                "ordering": ["code", "id"],
            },
        ),
        migrations.AddConstraint(
            model_name="registretraitement",
            constraint=models.UniqueConstraint(fields=("company", "code"), name="core_registretraitement_co_code"),
        ),
        migrations.AlterField(
            model_name="datasubjectrequest",
            name="kind",
            field=models.CharField(choices=[("acces", "Accès (export)"), ("effacement", "Effacement"), ("rectification", "Rectification")], max_length=12, verbose_name="Type"),
        ),
    ]
