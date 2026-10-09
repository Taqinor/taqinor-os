# ASAV71 — identifiants des connecteurs de supervision chiffrés au repos.
#
# ``MonitoringConfig.credentials`` passe de ``JSONField`` (jsonb, en clair) à
# ``EncryptedJSONField`` (TEXT chiffré, YHARD1 : key-gated par
# FIELD_ENCRYPTION_KEY) SUR PLACE : aucune colonne ajoutée ni retirée.
# Migration de données RÉVERSIBLE : l'avant ré-écrit chaque ligne par le champ
# (le jsonb converti en texte est alors chiffré) ; l'arrière remet le JSON
# clair dans la colonne (SQL brut, hors chiffrement) avant le retour en jsonb.
import json

import apps.monitoring.fields
from django.db import migrations


def chiffrer_existant(apps, schema_editor):
    Config = apps.get_model('monitoring', 'MonitoringConfig')
    for config in Config.objects.all().iterator():
        if config.credentials:
            # ``credentials`` est un dict déjà lu ; la sauvegarde passe par
            # ``get_prep_value`` qui chiffre.
            config.save(update_fields=['credentials'])


def restaurer_json_clair(apps, schema_editor):
    Config = apps.get_model('monitoring', 'MonitoringConfig')
    table = Config._meta.db_table
    with schema_editor.connection.cursor() as curseur:
        for config in Config.objects.all().iterator():
            curseur.execute(
                f'UPDATE {table} SET credentials = %s WHERE id = %s',
                [json.dumps(config.credentials or {}), config.pk])


class Migration(migrations.Migration):

    dependencies = [
        ('monitoring', '0010_asav70_fin_episode'),
    ]

    operations = [
        migrations.AlterField(
            model_name='monitoringconfig',
            name='credentials',
            field=apps.monitoring.fields.EncryptedJSONField(
                blank=True, default=dict),
        ),
        migrations.RunPython(chiffrer_existant, restaurer_json_clair),
    ]
