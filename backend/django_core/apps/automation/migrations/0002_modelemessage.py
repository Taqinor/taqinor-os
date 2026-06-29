# Generated for DC18 — store de modèles email/message d'automatisation.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0010_customuser_supervisor"),
        ("automation", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ModeleMessage",
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
                    "canal",
                    models.CharField(
                        choices=[
                            ("email", "Email"),
                            ("whatsapp", "WhatsApp"),
                            ("doc", "Document"),
                        ],
                        max_length=20,
                    ),
                ),
                ("objet", models.CharField(blank=True, default="", max_length=255)),
                ("corps", models.TextField(blank=True, default="")),
                ("enabled", models.BooleanField(default=True)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("date_modification", models.DateTimeField(auto_now=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="automation_modeles_message",
                        to="authentication.company",
                    ),
                ),
            ],
            options={
                "verbose_name": "Modèle de message",
                "verbose_name_plural": "Modèles de message",
                "ordering": ["canal", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="modelemessage",
            index=models.Index(
                fields=["company", "canal", "enabled"],
                name="automation_modmsg_idx",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="modelemessage",
            unique_together={("company", "canal")},
        ),
    ]
