# Generated for N93 — per-client document language (facture / devis in FR or AR).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0032_client_anonymization"),
    ]

    operations = [
        migrations.AddField(
            model_name="client",
            name="langue_document",
            field=models.CharField(
                choices=[("fr", "Français"), ("ar", "العربية")],
                default="fr",
                help_text="Langue des factures / devis générés pour ce client.",
                max_length=2,
                verbose_name="Langue des documents",
            ),
        ),
    ]
