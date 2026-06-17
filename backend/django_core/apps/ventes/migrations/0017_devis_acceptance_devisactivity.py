# N25 — acceptation explicite du devis (date + nom) + chatter DevisActivity.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ventes", "0016_facture_fichier_ubl"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="devis",
            name="date_acceptation",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="devis",
            name="accepte_par_nom",
            field=models.CharField(blank=True, default="", max_length=150),
        ),
        migrations.CreateModel(
            name="DevisActivity",
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
                    related_name="devis_activities",
                    to="authentication.company")),
                ("devis", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="activites", to="ventes.devis")),
                ("user", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="devis_activities",
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Activité devis",
                "verbose_name_plural": "Activités devis",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="devisactivity",
            index=models.Index(
                fields=["devis", "-created_at"],
                name="ventes_devisact_idx"),
        ),
    ]
