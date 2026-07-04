# XRH10 — Kiosque de pointage partagé (PIN/QR, tablette dépôt).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("rh", "0046_demande_rh"),
    ]

    operations = [
        migrations.AddField(
            model_name="dossieremploye",
            name="code_pointage",
            field=models.CharField(blank=True, default="", max_length=12),
        ),
        migrations.AddConstraint(
            model_name="dossieremploye",
            constraint=models.UniqueConstraint(
                condition=models.Q(("code_pointage", ""), _negated=True),
                fields=("company", "code_pointage"),
                name="rh_dossier_code_pointage_uniq",
            ),
        ),
        migrations.CreateModel(
            name="DeviceKiosque",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name="ID")),
                ("label", models.CharField(
                    blank=True, default="", max_length=120)),
                ("token_hash", models.CharField(
                    db_index=True, max_length=64, unique=True)),
                ("actif", models.BooleanField(default=True)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("derniere_utilisation", models.DateTimeField(
                    blank=True, null=True)),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="rh_devices_kiosque",
                    to="authentication.company")),
            ],
            options={
                "verbose_name": "Device kiosque",
                "verbose_name_plural": "Devices kiosque",
                "ordering": ["-date_creation"],
            },
        ),
        migrations.AddIndex(
            model_name="devicekiosque",
            index=models.Index(
                fields=["company", "actif"],
                name="rh_kiosque_comp_actif_idx"),
        ),
    ]
