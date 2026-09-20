# NTOBS25 — traçabilité d'un recalcul de rapport SLA : QUAND et POURQUOI.
# Deux champs ADDITIFS, vides par défaut : tous les snapshots existants valent
# « jamais recalculé », ce qui est exact. `genere_le` n'est pas touché — il
# garde la date de la première génération.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0072_ntobs34_trustcenter_alerte_expiration'),
    ]

    operations = [
        migrations.AddField(
            model_name='slasnapshot',
            name='recalcule_le',
            field=models.DateTimeField(
                blank=True, null=True,
                help_text='Vide = jamais recalculé depuis sa génération.',
                verbose_name='Recalculé le'),
        ),
        migrations.AddField(
            model_name='slasnapshot',
            name='raison_recalcul',
            field=models.CharField(
                blank=True, default='', max_length=255,
                help_text='Motif lisible du recalcul, affiché à côté du '
                          'chiffre corrigé (jamais un recalcul silencieux).',
                verbose_name='Raison du recalcul'),
        ),
    ]
