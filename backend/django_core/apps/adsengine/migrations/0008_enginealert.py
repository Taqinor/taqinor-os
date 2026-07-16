import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0023_yhard1_encrypt_totp_secret"),
        ("adsengine", "0007_weeklybrief"),
    ]

    operations = [
        migrations.CreateModel(
            name="EngineAlert",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name="ID"),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "alert_type",
                    models.CharField(
                        choices=[
                            ("anomalie", "Anomalie"),
                            ("garde_fou", "Violation de garde-fou"),
                            ("regle_inoperante", "Règle inopérante"),
                        ],
                        max_length=20, verbose_name="Type d'alerte"),
                ),
                (
                    "message",
                    models.TextField(verbose_name="Message (FR)"),
                ),
                (
                    "detail",
                    models.JSONField(
                        blank=True, default=dict, verbose_name="Détail"),
                ),
                (
                    "acknowledged",
                    models.BooleanField(
                        default=False, verbose_name="Acquittée"),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="%(app_label)s_%(class)s_set",
                        to="authentication.company",
                        verbose_name="Société"),
                ),
                (
                    "action",
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="alerts",
                        to="adsengine.engineaction",
                        verbose_name="Action liée"),
                ),
            ],
            options={
                "verbose_name": "Alerte moteur",
                "verbose_name_plural": "Alertes moteur",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="enginealert",
            index=models.Index(
                fields=["company", "acknowledged"],
                name="adseng_alert_co_ack_idx"),
        ),
    ]
