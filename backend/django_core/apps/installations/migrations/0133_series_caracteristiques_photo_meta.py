# Revue chantier 26/10/2026 (lane terrain) — relevé de série enrichi
# (caractéristiques de plaque + source de capture) et méta photo
# d'INTERVENTION (horodatage serveur + géoloc best-effort, instant client).
# Additif, revertable : aucun champ existant modifié.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0132_gps_consentement_geofence'),
    ]

    operations = [
        migrations.AddField(
            model_name='componentserial',
            name='caracteristiques',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='componentserial',
            name='capture_source',
            field=models.CharField(
                choices=[('scan', 'Scanné (code-barres / QR)'),
                         ('saisie', 'Saisi à la main'),
                         ('photo', 'Lu sur la photo de plaque')],
                default='saisie', max_length=10),
        ),
        migrations.AddField(
            model_name='photochecklistmeta',
            name='intervention',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='photo_metas',
                to='installations.intervention'),
        ),
        migrations.AddField(
            model_name='photochecklistmeta',
            name='horodatage_client',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
