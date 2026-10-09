# ACHT19 — horodatage de la notification client + webhook « livrée » d'une
# livraison (envoyés une seule fois). Additive, nullable, revertable.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0125_acht4_chantier_unique_devis'),
    ]

    operations = [
        migrations.AddField(
            model_name='livraison',
            name='notifie_livree_le',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
