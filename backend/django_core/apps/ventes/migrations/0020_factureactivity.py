# Chatter facture (FactureActivity) — trace avoir/paiement, additif.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ventes", "0019_emaillog"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="FactureActivity",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("kind", models.CharField(
                    choices=[("creation", "Création"),
                             ("modification", "Modification"),
                             ("note", "Note")], max_length=15)),
                ("field", models.CharField(blank=True, max_length=100, null=True)),
                ("field_label", models.CharField(
                    blank=True, max_length=150, null=True)),
                ("old_value", models.TextField(blank=True, null=True)),
                ("new_value", models.TextField(blank=True, null=True)),
                ("body", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="facture_activities",
                    to="authentication.company")),
                ("facture", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="activites", to="ventes.facture")),
                ("user", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="facture_activities",
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Activité facture",
                "verbose_name_plural": "Activités facture",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="factureactivity",
            index=models.Index(
                fields=["facture", "-created_at"],
                name="ventes_factact_idx"),
        ),
    ]
