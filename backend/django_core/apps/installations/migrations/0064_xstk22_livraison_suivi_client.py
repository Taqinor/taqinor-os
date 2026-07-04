# XSTK22 — suivi de livraison côté client : numéro de suivi + horodatage de
# la notification transit (garde l'envoi unique). Additive, nullable.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0063_xpur20_rfq_consultation'),
    ]

    operations = [
        migrations.AddField(
            model_name='livraison',
            name='numero_suivi',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='livraison',
            name='notifie_transit_le',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
