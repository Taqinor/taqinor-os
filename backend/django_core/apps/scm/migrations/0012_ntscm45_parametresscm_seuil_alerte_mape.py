# NTSCM45 — seuil d'alerte MAPE mensuel (notification ciblée sur écart de
# prévision important). Migration additive : défaut 40%, aucune régression
# pour une société qui n'a jamais rien configuré.
from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scm', '0011_ntscm34_module_toggle_off_existing'),
    ]

    operations = [
        migrations.AddField(
            model_name='parametresscm',
            name='seuil_alerte_mape_pct',
            field=models.DecimalField(
                decimal_places=2, default=Decimal('40'), max_digits=5,
                verbose_name="Seuil d'alerte écart de prévision — MAPE (%)"),
        ),
    ]
