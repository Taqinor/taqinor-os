# Generated for FG52 — Multi-currency quoting/invoicing.
# Adds devise (default MAD) + taux_change on Devis and Facture.
# Additive, reversible: no existing row is modified.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ventes", "0028_boncommande_lead_facture_lead"),
    ]

    operations = [
        # ── Devis ──
        migrations.AddField(
            model_name="devis",
            name="devise",
            field=models.CharField(
                default="MAD",
                help_text="Code ISO 4217 (ex. MAD, EUR, USD). Défaut MAD.",
                max_length=10,
                verbose_name="Devise",
            ),
        ),
        migrations.AddField(
            model_name="devis",
            name="taux_change",
            field=models.DecimalField(
                decimal_places=6,
                default=1,
                help_text="1 MAD = X devise (1 = MAD, sans conversion).",
                max_digits=12,
                verbose_name="Taux de change",
            ),
        ),
        # ── Facture ──
        migrations.AddField(
            model_name="facture",
            name="devise",
            field=models.CharField(
                default="MAD",
                help_text="Code ISO 4217 (ex. MAD, EUR, USD). Défaut MAD.",
                max_length=10,
                verbose_name="Devise",
            ),
        ),
        migrations.AddField(
            model_name="facture",
            name="taux_change",
            field=models.DecimalField(
                decimal_places=6,
                default=1,
                help_text="1 MAD = X devise (1 = MAD, sans conversion).",
                max_digits=12,
                verbose_name="Taux de change",
            ),
        ),
    ]
