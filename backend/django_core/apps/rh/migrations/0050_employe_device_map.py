# XRH13 — Import de pointages externes (pointeuse biométrique, CSV).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("rh", "0049_geofence_presence_chantier"),
    ]

    operations = [
        migrations.CreateModel(
            name="EmployeDeviceMap",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name="ID")),
                ("device_user_id", models.CharField(max_length=60)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="rh_device_maps",
                    to="authentication.company")),
                ("employe", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="device_maps", to="rh.dossieremploye")),
            ],
            options={
                "verbose_name": "Mappage pointeuse",
                "verbose_name_plural": "Mappages pointeuse",
                "ordering": ["device_user_id"],
                "unique_together": {("company", "device_user_id")},
            },
        ),
    ]
