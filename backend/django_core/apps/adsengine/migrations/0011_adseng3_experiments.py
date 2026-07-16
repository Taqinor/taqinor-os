import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """ADSENG3 — Modèles d'expérimentation (Experiment / ExperimentArm /
    ArmDailyStat / DecisionLog). Additif, company-scopé partout."""

    dependencies = [
        ("authentication", "0023_yhard1_encrypt_totp_secret"),
        ("adsengine", "0010_creativepolicy"),
    ]

    operations = [
        migrations.CreateModel(
            name="Experiment",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name="ID"),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=160, verbose_name="Nom")),
                (
                    "tested_variable",
                    models.CharField(
                        choices=[
                            ("hook", "Accroche (hook)"),
                            ("visuel", "Visuel"),
                            ("audience", "Audience"),
                            ("placement", "Placement"),
                            ("cta", "Appel à l'action (CTA)"),
                            ("autre", "Autre"),
                        ],
                        default="hook", max_length=12,
                        verbose_name="Variable testée"),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("brouillon", "Brouillon"),
                            ("en_cours", "En cours"),
                            ("en_pause", "En pause"),
                            ("terminee", "Terminée"),
                        ],
                        default="brouillon", max_length=12,
                        verbose_name="Statut"),
                ),
                (
                    "start_date",
                    models.DateField(
                        blank=True, null=True, verbose_name="Début"),
                ),
                (
                    "end_date",
                    models.DateField(
                        blank=True, null=True, verbose_name="Fin"),
                ),
                (
                    "notes",
                    models.TextField(
                        blank=True, default="", verbose_name="Notes"),
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
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="experiments",
                        to="adsengine.adcampaignmirror",
                        verbose_name="Campagne cible"),
                ),
                (
                    "adset",
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="experiments",
                        to="adsengine.adsetmirror",
                        verbose_name="Ad set cible"),
                ),
            ],
            options={
                "verbose_name": "Expérience publicitaire",
                "verbose_name_plural": "Expériences publicitaires",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="ExperimentArm",
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
                    "label",
                    models.CharField(
                        blank=True, default="", max_length=120,
                        verbose_name="Libellé"),
                ),
                (
                    "ad_id",
                    models.CharField(
                        blank=True, default="", max_length=64,
                        verbose_name="ID ad (Meta)"),
                ),
                (
                    "hook_id",
                    models.CharField(
                        blank=True, default="", max_length=64,
                        verbose_name="ID accroche"),
                ),
                (
                    "visual_id",
                    models.CharField(
                        blank=True, default="", max_length=64,
                        verbose_name="ID visuel"),
                ),
                (
                    "is_active",
                    models.BooleanField(default=True, verbose_name="Actif"),
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
                    "experiment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="arms",
                        to="adsengine.experiment",
                        verbose_name="Expérience"),
                ),
                (
                    "creative_asset",
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="experiment_arms",
                        to="adsengine.creativeasset",
                        verbose_name="Asset créatif"),
                ),
            ],
            options={
                "verbose_name": "Bras d'expérience",
                "verbose_name_plural": "Bras d'expérience",
                "ordering": ["experiment", "id"],
            },
        ),
        migrations.CreateModel(
            name="ArmDailyStat",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name="ID"),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("date", models.DateField(verbose_name="Date")),
                (
                    "impressions",
                    models.PositiveIntegerField(
                        default=0, verbose_name="Impressions"),
                ),
                (
                    "clicks",
                    models.PositiveIntegerField(
                        default=0, verbose_name="Clics"),
                ),
                (
                    "conversations",
                    models.PositiveIntegerField(
                        default=0, verbose_name="Conversations"),
                ),
                (
                    "spend",
                    models.DecimalField(
                        decimal_places=2, default=0, max_digits=14,
                        verbose_name="Dépense"),
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
                    "arm",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="daily_stats",
                        to="adsengine.experimentarm",
                        verbose_name="Bras"),
                ),
            ],
            options={
                "verbose_name": "Stat quotidienne de bras",
                "verbose_name_plural": "Stats quotidiennes de bras",
                "ordering": ["-date", "arm"],
            },
        ),
        migrations.CreateModel(
            name="DecisionLog",
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
                    "inputs",
                    models.JSONField(
                        blank=True, default=dict,
                        verbose_name="Entrées (instantané)"),
                ),
                (
                    "posteriors",
                    models.JSONField(
                        blank=True, default=dict,
                        verbose_name="Postérieurs"),
                ),
                (
                    "allocations",
                    models.JSONField(
                        blank=True, default=dict,
                        verbose_name="Allocations produites"),
                ),
                (
                    "summary_fr",
                    models.TextField(
                        blank=True, default="", verbose_name="Résumé (FR)"),
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
                    "experiment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="decisions",
                        to="adsengine.experiment",
                        verbose_name="Expérience"),
                ),
                (
                    "action",
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="decision_logs",
                        to="adsengine.engineaction",
                        verbose_name="Action produite"),
                ),
            ],
            options={
                "verbose_name": "Journal de décision",
                "verbose_name_plural": "Journaux de décision",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="experiment",
            index=models.Index(
                fields=["company", "status"],
                name="adseng_exp_co_status_idx"),
        ),
        migrations.AddIndex(
            model_name="experimentarm",
            index=models.Index(
                fields=["company", "ad_id"],
                name="adseng_arm_co_ad_idx"),
        ),
        migrations.AddConstraint(
            model_name="armdailystat",
            constraint=models.UniqueConstraint(
                fields=["company", "arm", "date"],
                name="uniq_adseng_arm_daily"),
        ),
        migrations.AddIndex(
            model_name="armdailystat",
            index=models.Index(
                fields=["arm", "date"],
                name="adseng_armstat_arm_dt_idx"),
        ),
        migrations.AddIndex(
            model_name="decisionlog",
            index=models.Index(
                fields=["company", "experiment"],
                name="adseng_declog_co_exp_idx"),
        ),
    ]
