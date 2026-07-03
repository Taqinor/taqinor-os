# XMKT32 — Sync Meta Lead Ads → leads CRM : nouvelle valeur de choix
# 'meta_lead_ads' sur Lead.source (aucun changement de schéma, choices only).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0035_xmkt21_lead_mql_assigned_at"),
    ]

    operations = [
        migrations.AlterField(
            model_name="lead",
            name="source",
            field=models.CharField(
                choices=[
                    ("os_native", "Créé dans TAQINOR"),
                    ("odoo_import_test", "Import test Odoo"),
                    ("site_web", "Site web"),
                    ("meta_lead_ads", "Meta Lead Ads"),
                ],
                default="os_native",
                max_length=32,
            ),
        ),
    ]
