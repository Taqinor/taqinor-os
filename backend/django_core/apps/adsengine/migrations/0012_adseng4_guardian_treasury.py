import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    """ADSENG4 — Gardien + trésorerie : champs additifs GuardrailConfig,
    extension EngineAlert (sévérité/cooldown/escalade), RulePolicy, AnomalyEvent,
    PacingState. Additif, company-scopé partout."""

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("authentication", "0023_yhard1_encrypt_totp_secret"),
        ("adsengine", "0011_adseng3_experiments"),
    ]

    operations = [
        migrations.AddField(
            model_name="guardrailconfig",
            name="monthly_budget_ceiling_mad",
            field=models.PositiveIntegerField(
                blank=True, null=True,
                verbose_name="Plafond budget mensuel (MAD)"),
        ),
        migrations.AddField(
            model_name="guardrailconfig",
            name="pacing_band_pct",
            field=models.PositiveIntegerField(
                default=15, verbose_name="Bande de pacing (%)"),
        ),
        migrations.AddField(
            model_name="guardrailconfig",
            name="exploration_floor_mad",
            field=models.PositiveIntegerField(
                default=20,
                verbose_name="Plancher d'exploration (MAD/jour)"),
        ),
        migrations.AddField(
            model_name="guardrailconfig",
            name="exploration_floor_pct",
            field=models.PositiveIntegerField(
                default=20, verbose_name="Plancher d'exploration (%)"),
        ),
        migrations.AddField(
            model_name="enginealert",
            name="severity",
            field=models.CharField(
                choices=[
                    ("critical", "Urgent"),
                    ("warning", "Attention"),
                    ("info", "Info"),
                ],
                default="warning", max_length=8, verbose_name="Sévérité"),
        ),
        migrations.AddField(
            model_name="enginealert",
            name="entity_key",
            field=models.CharField(
                blank=True, default="", max_length=80,
                verbose_name="Clé entité"),
        ),
        migrations.AddField(
            model_name="enginealert",
            name="cooldown_hours",
            field=models.PositiveIntegerField(
                default=0, verbose_name="Cooldown (heures)"),
        ),
        migrations.AddField(
            model_name="enginealert",
            name="unresolved_cycles",
            field=models.PositiveIntegerField(
                default=0, verbose_name="Cycles non résolus"),
        ),
        migrations.AddField(
            model_name="enginealert",
            name="resolved",
            field=models.BooleanField(
                default=False, verbose_name="Résolue"),
        ),
        migrations.AddIndex(
            model_name="enginealert",
            index=models.Index(
                fields=["company", "severity", "entity_key"],
                name="adseng_alert_sev_ent_idx"),
        ),
        migrations.CreateModel(
            name="RulePolicy",
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
                    "template_key",
                    models.CharField(
                        choices=[
                            ("cost_per_signature_ceiling",
                             "Plafond coût par signature"),
                            ("zero_delivery",
                             "Zéro delivery (dépense sans impression)"),
                            ("zero_results",
                             "Zéro résultat (délivre sans convertir)"),
                            ("frequency_high",
                             "Fréquence élevée (fatigue créative)"),
                            ("budget_pacing_breach",
                             "Franchissement d'enveloppe budgétaire"),
                        ],
                        max_length=48, verbose_name="Template de règle"),
                ),
                (
                    "enabled",
                    models.BooleanField(
                        default=False, verbose_name="Activée"),
                ),
                (
                    "mode",
                    models.CharField(
                        choices=[
                            ("propose", "Proposer"),
                            ("auto", "Automatique"),
                        ],
                        default="propose", max_length=8, verbose_name="Mode"),
                ),
                (
                    "dry_run",
                    models.BooleanField(
                        default=True, verbose_name="Simulation (dry-run)"),
                ),
                (
                    "conditions",
                    models.JSONField(
                        blank=True, default=dict,
                        verbose_name="Conditions (AND/OR)"),
                ),
                (
                    "params",
                    models.JSONField(
                        blank=True, default=dict,
                        verbose_name="Paramètres"),
                ),
                (
                    "cadence_hours",
                    models.PositiveIntegerField(
                        default=6, verbose_name="Cadence (heures)"),
                ),
                (
                    "cooldown_hours",
                    models.PositiveIntegerField(
                        default=0,
                        verbose_name="Cooldown par entité (heures)"),
                ),
                (
                    "last_evaluated_at",
                    models.DateTimeField(
                        blank=True, null=True,
                        verbose_name="Dernière évaluation"),
                ),
                (
                    "last_result",
                    models.JSONField(
                        blank=True, default=dict,
                        verbose_name="Dernier résultat (audit)"),
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
                    "created_by",
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="adsengine_rule_policies",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Créée par"),
                ),
            ],
            options={
                "verbose_name": "Règle de garde-fou",
                "verbose_name_plural": "Règles de garde-fou",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="AnomalyEvent",
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
                    "kind",
                    models.CharField(
                        choices=[
                            ("zero_delivery", "Zéro delivery"),
                            ("zero_results", "Zéro résultat"),
                            ("cost_spike", "Pic de coût"),
                            ("frequency_high", "Fréquence élevée"),
                            ("autre", "Autre"),
                        ],
                        max_length=16, verbose_name="Type d'anomalie"),
                ),
                (
                    "entity_type",
                    models.CharField(
                        blank=True, default="", max_length=16,
                        verbose_name="Type d'entité (campaign/adset/ad)"),
                ),
                (
                    "entity_meta_id",
                    models.CharField(
                        blank=True, default="", max_length=64,
                        verbose_name="ID Meta entité"),
                ),
                (
                    "severity",
                    models.CharField(
                        choices=[
                            ("critical", "Urgent"),
                            ("warning", "Attention"),
                            ("info", "Info"),
                        ],
                        default="warning", max_length=8,
                        verbose_name="Sévérité"),
                ),
                (
                    "message_fr",
                    models.TextField(
                        blank=True, default="", verbose_name="Message (FR)"),
                ),
                (
                    "detail",
                    models.JSONField(
                        blank=True, default=dict, verbose_name="Détail"),
                ),
                (
                    "resolved",
                    models.BooleanField(
                        default=False, verbose_name="Résolue"),
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
                    "rule_policy",
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="anomalies",
                        to="adsengine.rulepolicy",
                        verbose_name="Règle détectrice"),
                ),
                (
                    "alert",
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="anomalies",
                        to="adsengine.enginealert",
                        verbose_name="Alerte émise"),
                ),
            ],
            options={
                "verbose_name": "Anomalie détectée",
                "verbose_name_plural": "Anomalies détectées",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="PacingState",
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
                    "period_start",
                    models.DateField(
                        verbose_name="Début de période (mois)"),
                ),
                (
                    "monthly_budget_ceiling_mad",
                    models.PositiveIntegerField(
                        blank=True, null=True,
                        verbose_name="Plafond mensuel (MAD)"),
                ),
                (
                    "spend_to_date",
                    models.DecimalField(
                        decimal_places=2, default=0, max_digits=14,
                        verbose_name="Dépense à date"),
                ),
                (
                    "expected_spend_to_date",
                    models.DecimalField(
                        decimal_places=2, default=0, max_digits=14,
                        verbose_name="Dépense attendue à date"),
                ),
                (
                    "forecast_spend",
                    models.DecimalField(
                        decimal_places=2, default=0, max_digits=14,
                        verbose_name="Prévision de dépense (fin de mois)"),
                ),
                (
                    "pacing_ratio",
                    models.DecimalField(
                        blank=True, decimal_places=4, max_digits=8,
                        null=True, verbose_name="Ratio de pacing"),
                ),
                (
                    "state",
                    models.CharField(
                        choices=[
                            ("on_track", "Dans les clous"),
                            ("under_pacing", "Sous-rythme"),
                            ("over_pacing", "Sur-rythme"),
                            ("breach_imminent", "Franchissement imminent"),
                            ("paused_for_month", "En pause pour le mois"),
                        ],
                        default="on_track", max_length=20,
                        verbose_name="État"),
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
                "verbose_name": "État de pacing",
                "verbose_name_plural": "États de pacing",
                "ordering": ["-period_start", "-created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="rulepolicy",
            constraint=models.UniqueConstraint(
                fields=["company", "template_key"],
                name="uniq_adseng_rule_template"),
        ),
        migrations.AddIndex(
            model_name="rulepolicy",
            index=models.Index(
                fields=["company", "enabled"],
                name="adseng_rule_co_en_idx"),
        ),
        migrations.AddIndex(
            model_name="anomalyevent",
            index=models.Index(
                fields=["company", "resolved"],
                name="adseng_anom_co_res_idx"),
        ),
        migrations.AddIndex(
            model_name="anomalyevent",
            index=models.Index(
                fields=["company", "entity_meta_id"],
                name="adseng_anom_co_ent_idx"),
        ),
        migrations.AddConstraint(
            model_name="pacingstate",
            constraint=models.UniqueConstraint(
                fields=["company", "period_start"],
                name="uniq_adseng_pacing_period"),
        ),
    ]
