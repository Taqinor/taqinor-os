# NTEDU26 — Facturation cantine dans l'échéancier (composante isolée pour un
# recalcul propre des lignes futures — jamais rétroactif).

from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('education', '0011_eleve_allergies_menucantine_inscriptioncantine'),
    ]

    operations = [
        migrations.AddField(
            model_name='ligneecheance',
            name='cantine_montant',
            field=models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=10, verbose_name='Montant cantine (inclus)'),
        ),
    ]
