import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    """ADSENG5 — Créa + vol : champs composants sur CreativeAsset,
    CreativeGenerationBatch, CreativeBacklogItem, FlightPlan/FlightPhase,
    ReconciliationSnapshot. Additif, company-scopé partout."""

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("authentication", "0023_yhard1_encrypt_totp_secret"),
        ("adsengine", "0012_adseng4_guardian_treasury"),
    ]

    operations = [
        migrations.AddField(
            model_name="creativeasset",
            name="hook_id",
            field=models.CharField(
                blank=True, default="", max_length=64,
                verbose_name="ID accroche"),
        ),
        migrations.AddField(
            model_name="creativeasset",
            name="hook_text",
            field=models.TextField(
                blank=True, default="", verbose_name="Texte accroche"),
        ),
        migrations.AddField(
            model_name="creativeasset",
            name="primary_text",
            field=models.TextField(
                blank=True, default="", verbose_name="Texte principal"),
        ),
        migrations.AddField(
            model_name="creativeasset",
            name="visual_asset_key",
            field=models.CharField(
                blank=True, default="", max_length=255,
                verbose_name="Clé MinIO du visuel"),
        ),
        migrations.AddField(
            model_name="creativeasset",
            name="cta",
            field=models.CharField(
                blank=True, default="", max_length=40,
                verbose_name="Appel à l'action (CTA)"),
        ),
        migrations.CreateModel(
            name="CreativeGenerationBatch",
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
                    "visual_ids",
                    models.JSONField(
                        blank=True, default=list,
                        verbose_name="IDs visuels candidats"),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("en_attente", "En attente"),
                            ("approuvee", "Approuvé"),
                            ("rejetee", "Rejeté"),
                        ],
                        default="en_attente", max_length=12,
                        verbose_name="Statut"),
                ),
                (
                    "approved_at",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="Décidé le"),
                ),
                (
                    "note",
                    models.TextField(
                        blank=True, default="", verbose_name="Note"),
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
                    "source_hook_asset",
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="generation_batches",
                        to="adsengine.creativeasset",
                        verbose_name="Asset accroche source"),
                ),
                (
                    "approved_by",
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="adsengine_batches_approuves",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Décidé par"),
                ),
            ],
            options={
                "verbose_name": "Lot de génération créative",
                "verbose_name_plural": "Lots de génération créative",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="CreativeBacklogItem",
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
                    "source",
                    models.CharField(
                        choices=[
                            ("manuel", "Upload manuel"),
                            ("recombinaison", "Recombinaison"),
                        ],
                        default="manuel", max_length=16,
                        verbose_name="Provenance"),
                ),
                (
                    "earliest_date",
                    models.DateField(
                        blank=True, null=True,
                        verbose_name="Date au plus tôt"),
                ),
                (
                    "seasonal_tag",
                    models.CharField(
                        blank=True, default="", max_length=40,
                        verbose_name="Tag saisonnier"),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("en_file", "En file"),
                            ("programme", "Programmé"),
                            ("publie", "Publié"),
                            ("retire", "Retiré"),
                        ],
                        default="en_file", max_length=12,
                        verbose_name="Statut file"),
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
                    "asset",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="backlog_items",
                        to="adsengine.creativeasset",
                        verbose_name="Asset"),
                ),
                (
                    "batch",
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="backlog_items",
                        to="adsengine.creativegenerationbatch",
                        verbose_name="Lot source"),
                ),
                (
                    "target_campaign",
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="backlog_items",
                        to="adsengine.adcampaignmirror",
                        verbose_name="Campagne cible"),
                ),
            ],
            options={
                "verbose_name": "Item de backlog créatif",
                "verbose_name_plural": "Items de backlog créatif",
                "ordering": ["earliest_date", "id"],
            },
        ),
        migrations.CreateModel(
            name="FlightPlan",
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
                    "objective",
                    models.CharField(
                        blank=True, default="", max_length=64,
                        verbose_name="Objectif"),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("brouillon", "Brouillon"),
                            ("actif", "Actif"),
                            ("termine", "Terminé"),
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
            ],
            options={
                "verbose_name": "Plan de vol",
                "verbose_name_plural": "Plans de vol",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="FlightPhase",
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
                    "order",
                    models.PositiveIntegerField(
                        default=0, verbose_name="Ordre"),
                ),
                ("name", models.CharField(max_length=120, verbose_name="Nom")),
                (
                    "tested_variable",
                    models.CharField(
                        blank=True, default="", max_length=12,
                        verbose_name="Variable testée"),
                ),
                (
                    "launch_template",
                    models.CharField(
                        blank=True, default="", max_length=64,
                        verbose_name="Template de lancement"),
                ),
                (
                    "budget_mad",
                    models.PositiveIntegerField(
                        default=0, verbose_name="Budget (MAD)"),
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
                    "num_arms",
                    models.PositiveSmallIntegerField(
                        default=2, verbose_name="Nombre de bras"),
                ),
                (
                    "week_span",
                    models.PositiveSmallIntegerField(
                        default=3, verbose_name="Durée (semaines)"),
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
                    "plan",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="phases",
                        to="adsengine.flightplan",
                        verbose_name="Plan"),
                ),
            ],
            options={
                "verbose_name": "Phase de vol",
                "verbose_name_plural": "Phases de vol",
                "ordering": ["plan", "order", "id"],
            },
        ),
        migrations.CreateModel(
            name="ReconciliationSnapshot",
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
                    "meta_leads",
                    models.PositiveIntegerField(
                        default=0, verbose_name="Leads (côté Meta)"),
                ),
                (
                    "erp_leads",
                    models.PositiveIntegerField(
                        default=0, verbose_name="Leads (côté ERP)"),
                ),
                (
                    "meta_spend",
                    models.DecimalField(
                        decimal_places=2, default=0, max_digits=14,
                        verbose_name="Dépense (côté Meta)"),
                ),
                (
                    "delta_leads",
                    models.IntegerField(
                        default=0,
                        verbose_name="Écart de leads (Meta − ERP)"),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("ok", "Cohérent"),
                            ("ecart", "Écart"),
                            ("a_verifier", "À vérifier"),
                        ],
                        default="ok", max_length=12, verbose_name="Statut"),
                ),
                (
                    "detail",
                    models.JSONField(
                        blank=True, default=dict, verbose_name="Détail"),
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
                        related_name="reconciliations",
                        to="adsengine.adcampaignmirror",
                        verbose_name="Campagne"),
                ),
            ],
            options={
                "verbose_name": "Instantané de réconciliation",
                "verbose_name_plural": "Instantanés de réconciliation",
                "ordering": ["-date", "-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="creativegenerationbatch",
            index=models.Index(
                fields=["company", "status"],
                name="adseng_batch_co_st_idx"),
        ),
        migrations.AddIndex(
            model_name="creativebacklogitem",
            index=models.Index(
                fields=["company", "status"],
                name="adseng_backlog_co_st_idx"),
        ),
        migrations.AddIndex(
            model_name="flightplan",
            index=models.Index(
                fields=["company", "status"],
                name="adseng_flight_co_st_idx"),
        ),
        migrations.AddIndex(
            model_name="flightphase",
            index=models.Index(
                fields=["plan", "order"],
                name="adseng_phase_plan_ord_idx"),
        ),
        migrations.AddIndex(
            model_name="reconciliationsnapshot",
            index=models.Index(
                fields=["company", "date"],
                name="adseng_recon_co_dt_idx"),
        ),
    ]
