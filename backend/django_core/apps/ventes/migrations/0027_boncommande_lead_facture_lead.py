# Generated for U12 — direct lead FK on Facture & BonCommande.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0004_lead_client_lead_ete_differente_lead_facture_ete_and_more"),
        ("ventes", "0026_paymentlink"),
    ]

    operations = [
        migrations.AddField(
            model_name="boncommande",
            name="lead",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="bons_commande_directs",
                to="crm.lead",
            ),
        ),
        migrations.AddField(
            model_name="facture",
            name="lead",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="factures_directes",
                to="crm.lead",
            ),
        ),
    ]
