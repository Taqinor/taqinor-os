"""AACQ76 — Empreinte de la version APPROUVÉE d'une action du moteur.

ADDITIVE + données : une colonne ``approved_fingerprint`` (défaut vide), puis
l'empreinte (SHA-256 de ``kind`` + ``payload``, clés triées — même calcul que
``EngineAction.fingerprint_of``) posée sur les lignes déjà ``approuvee`` pour
qu'elles restent applicables. Revertable : le retour arrière supprime la
colonne (l'étape de données est un no-op en arrière).
"""
import hashlib
import json

from django.db import migrations, models


def _fingerprint(kind, payload):
    blob = json.dumps({'kind': kind or '', 'payload': payload or {}},
                      sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(blob.encode('utf-8')).hexdigest()


def poser_empreintes(apps, schema_editor):
    EngineAction = apps.get_model('adsengine', 'EngineAction')
    for action in (EngineAction.objects.filter(status='approuvee')
                   .only('pk', 'kind', 'payload').iterator()):
        EngineAction.objects.filter(pk=action.pk).update(
            approved_fingerprint=_fingerprint(action.kind, action.payload))


class Migration(migrations.Migration):

    dependencies = [
        ('adsengine', '0058_aacq16_budget_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='engineaction',
            name='approved_fingerprint',
            field=models.CharField(
                blank=True, default='', max_length=64,
                verbose_name='Empreinte de la version approuvée'),
        ),
        migrations.RunPython(poser_empreintes, migrations.RunPython.noop),
    ]
