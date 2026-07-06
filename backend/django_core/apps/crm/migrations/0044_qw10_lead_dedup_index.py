# QW10 — Index-backed dedup: normalized phone/email columns + indexes,
# backfilled for existing rows. Additive, reversible (backfill is a no-op on
# reverse — the columns are simply dropped).

import re

from django.db import migrations, models


def _normalize_phone(value):
    digits = re.sub(r'\D', '', str(value or ''))
    if not digits:
        return ''
    if digits.startswith('00'):
        digits = digits[2:]
    if digits.startswith('212'):
        digits = digits[3:]
    return digits.lstrip('0')


def _normalize_email(value):
    return str(value or '').strip().lower()


def backfill_dedup_columns(apps, schema_editor):
    Lead = apps.get_model('crm', 'Lead')
    batch = []
    for lead in Lead.objects.all().only('id', 'telephone', 'email'):
        lead.phone_normalise = _normalize_phone(lead.telephone)
        lead.email_normalise = _normalize_email(lead.email)
        batch.append(lead)
        if len(batch) >= 500:
            Lead.objects.bulk_update(batch, ['phone_normalise', 'email_normalise'])
            batch = []
    if batch:
        Lead.objects.bulk_update(batch, ['phone_normalise', 'email_normalise'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0043_qw3_lead_contact_preference"),
    ]

    operations = [
        migrations.AddField(
            model_name="lead",
            name="phone_normalise",
            field=models.CharField(
                blank=True, default="", db_index=True, max_length=20,
                verbose_name="Téléphone normalisé (dédup)",
            ),
        ),
        migrations.AddField(
            model_name="lead",
            name="email_normalise",
            field=models.CharField(
                blank=True, default="", db_index=True, max_length=254,
                verbose_name="Email normalisé (dédup)",
            ),
        ),
        # NB — les deux index composites (company, phone/email_normalise) sont
        # posés CONCURREMMENT dans 0049 (YOPSB6) pour ne pas verrouiller
        # crm_lead en écriture ; ici on se limite aux colonnes + backfill.
        migrations.RunPython(backfill_dedup_columns, noop_reverse),
    ]
