# XSAL7 — Lead.montant_estime + date_cloture_prevue (weighted pipeline
# forecast pre-devis). Additive + nullable, reversible via the automatic
# RemoveField reverse.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0044_qw10_lead_contact_normalized_index"),
    ]

    operations = [
        migrations.AddField(
            model_name="lead",
            name="montant_estime",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=12, null=True,
                help_text="Estimation libre du commercial avant devis — "
                          "contribue au forecast pondéré tant qu'aucun "
                          "devis actif n'existe.",
                verbose_name="Montant estimé (MAD)",
            ),
        ),
        migrations.AddField(
            model_name="lead",
            name="date_cloture_prevue",
            field=models.DateField(
                blank=True, null=True,
                verbose_name="Date de clôture prévue",
            ),
        ),
    ]
