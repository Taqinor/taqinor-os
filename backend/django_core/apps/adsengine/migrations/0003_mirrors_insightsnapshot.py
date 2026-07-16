import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("authentication", "0023_yhard1_encrypt_totp_secret"),
        ("adsengine", "0002_guardrailconfig"),
    ]

    operations = [
        migrations.CreateModel(
            name="AdCampaignMirror",
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
                    "meta_id",
                    models.CharField(max_length=64, verbose_name="ID Meta"),
                ),
                (
                    "name",
                    models.CharField(
                        blank=True, default="", max_length=255,
                        verbose_name="Nom"),
                ),
                (
                    "status",
                    models.CharField(
                        blank=True, default="", max_length=32,
                        verbose_name="Statut Meta"),
                ),
                (
                    "objective",
                    models.CharField(
                        blank=True, default="", max_length=64,
                        verbose_name="Objectif"),
                ),
                (
                    "budget",
                    models.DecimalField(
                        blank=True, decimal_places=2, max_digits=14,
                        null=True,
                        verbose_name="Budget (unités mineures Meta)"),
                ),
                (
                    "created_via_engine",
                    models.BooleanField(
                        default=False, verbose_name="Créée par le moteur"),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="%(app_label)s_%(class)s_set",
                        to="authentication.company",
                        verbose_name="Société"),
                ),
            ],
            options={
                "verbose_name": "Miroir de campagne",
                "verbose_name_plural": "Miroirs de campagne",
                "ordering": ["-created_at"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("company", "meta_id"),
                        name="uniq_adsengine_campaign_meta"),
                ],
            },
        ),
        migrations.CreateModel(
            name="AdSetMirror",
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
                    "meta_id",
                    models.CharField(max_length=64, verbose_name="ID Meta"),
                ),
                (
                    "name",
                    models.CharField(
                        blank=True, default="", max_length=255,
                        verbose_name="Nom"),
                ),
                (
                    "status",
                    models.CharField(
                        blank=True, default="", max_length=32,
                        verbose_name="Statut Meta"),
                ),
                (
                    "budget",
                    models.DecimalField(
                        blank=True, decimal_places=2, max_digits=14,
                        null=True,
                        verbose_name="Budget (unités mineures Meta)"),
                ),
                (
                    "created_via_engine",
                    models.BooleanField(
                        default=False, verbose_name="Créé par le moteur"),
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
                    "campaign",
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="adsets",
                        to="adsengine.adcampaignmirror",
                        verbose_name="Campagne"),
                ),
            ],
            options={
                "verbose_name": "Miroir d'ad set",
                "verbose_name_plural": "Miroirs d'ad set",
                "ordering": ["-created_at"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("company", "meta_id"),
                        name="uniq_adsengine_adset_meta"),
                ],
            },
        ),
        migrations.CreateModel(
            name="AdMirror",
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
                    "meta_id",
                    models.CharField(max_length=64, verbose_name="ID Meta"),
                ),
                (
                    "name",
                    models.CharField(
                        blank=True, default="", max_length=255,
                        verbose_name="Nom"),
                ),
                (
                    "status",
                    models.CharField(
                        blank=True, default="", max_length=32,
                        verbose_name="Statut Meta"),
                ),
                (
                    "created_via_engine",
                    models.BooleanField(
                        default=False, verbose_name="Créée par le moteur"),
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
                    "adset",
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ads",
                        to="adsengine.adsetmirror",
                        verbose_name="Ad set"),
                ),
            ],
            options={
                "verbose_name": "Miroir d'ad",
                "verbose_name_plural": "Miroirs d'ad",
                "ordering": ["-created_at"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("company", "meta_id"),
                        name="uniq_adsengine_ad_meta"),
                ],
            },
        ),
        migrations.CreateModel(
            name="InsightSnapshot",
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
                    "object_id",
                    models.PositiveIntegerField(verbose_name="ID cible"),
                ),
                ("date", models.DateField(verbose_name="Date")),
                (
                    "spend",
                    models.DecimalField(
                        blank=True, decimal_places=2, max_digits=14,
                        null=True, verbose_name="Dépense"),
                ),
                (
                    "results",
                    models.PositiveIntegerField(
                        blank=True, null=True, verbose_name="Résultats"),
                ),
                (
                    "frequency",
                    models.DecimalField(
                        blank=True, decimal_places=2, max_digits=6,
                        null=True, verbose_name="Fréquence"),
                ),
                (
                    "cpl",
                    models.DecimalField(
                        blank=True, decimal_places=2, max_digits=12,
                        null=True, verbose_name="Coût par lead"),
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
                    "content_type",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="contenttypes.contenttype",
                        verbose_name="Type de cible"),
                ),
            ],
            options={
                "verbose_name": "Instantané de performance",
                "verbose_name_plural": "Instantanés de performance",
                "ordering": ["-date", "-created_at"],
                "indexes": [
                    models.Index(
                        fields=["content_type", "object_id"],
                        name="adseng_insight_ct_obj_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("company", "content_type", "object_id", "date"),
                        name="uniq_adsengine_insight_snap"),
                ],
            },
        ),
    ]
