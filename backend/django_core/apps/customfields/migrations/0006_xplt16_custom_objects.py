# XPLT16 — objets personnalisés no-code (CustomObjectDef + CustomRecord).

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("authentication", "0001_initial"),
        ("customfields", "0005_xplt15_conditions"),
    ]

    operations = [
        migrations.AlterField(
            model_name="customfielddef",
            name="module",
            field=models.CharField(
                choices=[
                    ("lead", "Lead"),
                    ("client", "Client"),
                    ("produit", "Produit"),
                    ("devis", "Devis"),
                    ("installation", "Chantier"),
                    ("ticket", "Ticket SAV"),
                    ("document", "Document GED"),
                    ("fournisseur", "Fournisseur"),
                    ("employe", "Employé"),
                ],
                max_length=60,
            ),
        ),
        migrations.CreateModel(
            name="CustomObjectDef",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                            serialize=False, verbose_name="ID")),
                ("code", models.SlugField(max_length=50)),
                ("libelle", models.CharField(max_length=120)),
                ("icone", models.CharField(blank=True, default="", max_length=8)),
                ("actif", models.BooleanField(default=True)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="custom_objects", to="authentication.company")),
                ("created_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="custom_objects_crees",
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Objet personnalisé",
                "verbose_name_plural": "Objets personnalisés",
                "ordering": ["libelle"],
            },
        ),
        migrations.AlterUniqueTogether(
            name="customobjectdef",
            unique_together={("company", "code")},
        ),
        migrations.CreateModel(
            name="CustomRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                            serialize=False, verbose_name="ID")),
                ("data", models.JSONField(blank=True, default=dict)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("date_modification", models.DateTimeField(auto_now=True)),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="custom_records", to="authentication.company")),
                ("created_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="custom_records_crees",
                    to=settings.AUTH_USER_MODEL)),
                ("objet", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="records", to="customfields.customobjectdef")),
            ],
            options={
                "verbose_name": "Enregistrement personnalisé",
                "verbose_name_plural": "Enregistrements personnalisés",
                "ordering": ["-date_creation"],
            },
        ),
    ]
