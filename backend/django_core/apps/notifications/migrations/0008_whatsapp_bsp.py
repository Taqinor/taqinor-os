# Generated for QJ23 — WhatsApp BSP scaffold (flag-gated, default manual wa.me)
# Additive migration only: two new tables, zero destructive changes.

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0007_alter_notification_event_type_and_more"),
        ("authentication", "0010_customuser_supervisor"),
    ]

    operations = [
        # 1. WhatsAppTemplate — BSP template registry, company-scoped.
        migrations.CreateModel(
            name="WhatsAppTemplate",
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
                    "name",
                    models.CharField(
                        max_length=100, verbose_name="Nom du gabarit Meta"
                    ),
                ),
                (
                    "body_fr",
                    models.TextField(
                        blank=True,
                        default="",
                        verbose_name="Corps FR (aide-mémoire)",
                    ),
                ),
                (
                    "language",
                    models.CharField(
                        default="fr", max_length=10, verbose_name="Langue"
                    ),
                ),
                (
                    "active",
                    models.BooleanField(default=True, verbose_name="Actif"),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="whatsapp_bsp_templates",
                        to="authentication.company",
                    ),
                ),
            ],
            options={
                "verbose_name": "Gabarit WhatsApp BSP",
                "verbose_name_plural": "Gabarits WhatsApp BSP",
                "ordering": ["name"],
            },
        ),
        migrations.AddConstraint(
            model_name="whatsapptemplate",
            constraint=models.UniqueConstraint(
                fields=["company", "name", "language"],
                name="notif_wa_tpl_company_name_lang_uniq",
            ),
        ),
        migrations.AddIndex(
            model_name="whatsapptemplate",
            index=models.Index(
                fields=["company", "active"],
                name="notif_wa_tpl_company_active_idx",
            ),
        ),
        # 2. WhatsAppMessageLog — delivery/receipt log, company-scoped.
        migrations.CreateModel(
            name="WhatsAppMessageLog",
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
                    "recipient",
                    models.CharField(max_length=30, verbose_name="Destinataire"),
                ),
                (
                    "body",
                    models.TextField(blank=True, default="", verbose_name="Corps"),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("queued", "En attente"),
                            ("sent", "Envoyé"),
                            ("delivered", "Distribué"),
                            ("read", "Lu"),
                            ("failed", "Échec"),
                            ("manual", "Manuel (wa.me)"),
                        ],
                        default="manual",
                        max_length=20,
                        verbose_name="Statut",
                    ),
                ),
                (
                    "provider",
                    models.CharField(
                        choices=[
                            ("manual", "Manuel (wa.me)"),
                            ("bsp", "BSP (API WhatsApp Business)"),
                        ],
                        default="manual",
                        max_length=20,
                        verbose_name="Fournisseur",
                    ),
                ),
                (
                    "external_id",
                    models.CharField(
                        blank=True,
                        db_index=True,
                        default="",
                        max_length=255,
                        verbose_name="ID externe Meta",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="whatsapp_message_logs",
                        to="authentication.company",
                    ),
                ),
                (
                    "template",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="message_logs",
                        to="notifications.whatsapptemplate",
                        verbose_name="Gabarit BSP",
                    ),
                ),
            ],
            options={
                "verbose_name": "Journal WhatsApp",
                "verbose_name_plural": "Journal WhatsApp",
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="whatsappmessagelog",
            index=models.Index(
                fields=["company", "recipient", "status"],
                name="notif_wa_log_company_recip_st_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="whatsappmessagelog",
            index=models.Index(
                fields=["company", "created_at"],
                name="notif_wa_log_company_created_idx",
            ),
        ),
    ]
