# ACRM32 (C-ACRM-027) — clé normalisée du WhatsApp du lead, indexée, et
# backfill des lignes existantes. Additive, revertable : l'inverse du
# backfill est un no-op (la colonne est simplement retirée). L'index
# (société, whatsapp_normalise) est posé CONCURREMMENT par 0132 (YOPSB6).

import re

from django.db import migrations, models


def _normalize_phone(value):
    """Copie FIGÉE de ``crm.services.normalize_phone`` (une migration ne lit
    jamais le code vivant)."""
    digits = re.sub(r'\D', '', str(value or ''))
    if not digits:
        return ''
    if digits.startswith('00'):
        digits = digits[2:]
    if digits.startswith('212'):
        digits = digits[3:]
    return digits.lstrip('0')


def backfill_whatsapp_normalise(apps, schema_editor):
    Lead = apps.get_model('crm', 'Lead')
    batch = []
    qs = (Lead.objects.exclude(whatsapp__isnull=True)
          .exclude(whatsapp='').only('id', 'whatsapp'))
    for lead in qs.iterator():
        lead.whatsapp_normalise = _normalize_phone(lead.whatsapp)[:20]
        batch.append(lead)
        if len(batch) >= 500:
            Lead.objects.bulk_update(batch, ['whatsapp_normalise'])
            batch = []
    if batch:
        Lead.objects.bulk_update(batch, ['whatsapp_normalise'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0130_acrm25_motif_standard_propose'),
    ]

    operations = [
        migrations.AddField(
            model_name='lead',
            name='whatsapp_normalise',
            field=models.CharField(
                blank=True, default='', max_length=20,
                verbose_name='WhatsApp normalisé (dédup)'),
        ),
        migrations.RunPython(backfill_whatsapp_normalise, noop_reverse),
    ]
