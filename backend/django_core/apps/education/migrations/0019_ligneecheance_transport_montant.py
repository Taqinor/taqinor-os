# NTEDU24 — Facturation transport dans l'échéancier (composante isolée pour
# un recalcul propre des lignes futures — jamais rétroactif, même principe
# que cantine_montant/NTEDU26).

from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('education', '0018_ntedu23_transport_scolaire'),
    ]

    operations = [
        migrations.AddField(
            model_name='ligneecheance',
            name='transport_montant',
            field=models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=10, verbose_name='Montant transport (inclus)'),
        ),
    ]
