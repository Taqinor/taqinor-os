"""QJ6 — Champ score (IntegerField nullable) + index (company, score) sur Lead.

Additif et nullable : les leads existants auront score=NULL jusqu'au prochain
enregistrement (ou backfill manuel). Le sérialiseur continue d'exposer la valeur
calculée à la volée via SerializerMethodField ; le champ stocké sert uniquement
au tri pagination-safe (?ordering=-score).
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0025_alter_lead_raccordement'),
    ]

    operations = [
        migrations.AddField(
            model_name='lead',
            name='score',
            field=models.IntegerField(
                blank=True,
                null=True,
                verbose_name='Score de qualité',
                help_text='Score 0–100 calculé automatiquement (voir scoring.py).',
            ),
        ),
        migrations.AddIndex(
            model_name='lead',
            index=models.Index(fields=['company', 'score'], name='crm_lead_company_score_idx'),
        ),
    ]
