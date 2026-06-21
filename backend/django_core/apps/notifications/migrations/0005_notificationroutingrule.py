# Generated manually for FG4 — NotificationRoutingRule

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0004_vapidkeypair"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="NotificationRoutingRule",
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
                    "event_type",
                    models.CharField(
                        choices=[
                            ("lead_assigned", "Nouveau lead assigné"),
                            ("devis_accepted", "Devis accepté"),
                            ("chantier_due", "Chantier à installer"),
                            ("facture_overdue", "Facture en retard"),
                            ("warranty_expiring", "Garantie bientôt expirée"),
                            ("maintenance_due", "Visite de maintenance due"),
                            ("stock_low", "Stock bas"),
                            ("sav_ticket_opened", "Ticket SAV ouvert"),
                            ("sav_ticket_breaching", "Ticket SAV proche de son délai"),
                            ("digest", "Récapitulatif"),
                        ],
                        max_length=40,
                        verbose_name="Type d'événement",
                    ),
                ),
                (
                    "target_role",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("admin", "Administrateur"),
                            ("responsable", "Responsable"),
                            ("normal", "Utilisateur normal"),
                        ],
                        max_length=20,
                        null=True,
                        verbose_name="Rôle cible",
                    ),
                ),
                (
                    "enabled",
                    models.BooleanField(default=True, verbose_name="Actif"),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notification_routing_rules",
                        to="authentication.company",
                    ),
                ),
                (
                    "target_user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notification_routing_rules",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Utilisateur cible",
                    ),
                ),
            ],
            options={
                "verbose_name": "Règle de routage des notifications",
                "verbose_name_plural": "Règles de routage des notifications",
                "ordering": ["event_type", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="notificationroutingrule",
            index=models.Index(
                fields=["company", "event_type", "enabled"],
                name="notificatio_company_f47d25_idx",
            ),
        ),
    ]
