"""ZGED15 — Backfill des références lisibles des documents existants.

Migration de DONNÉES uniquement (le champ `reference` a déjà été ajouté,
blank par défaut, par 0042). Chaque document sans référence reçoit une valeur
DISTINCTE — jamais une valeur unique en masse (piège documenté :
`deploy_migration_gotchas`) — dérivée de son mois de création réel
(`created_at`), avec un compteur par (société, mois) tenu EN MÉMOIRE pendant
le backfill (jamais `count()+1` en base : ce compteur ne sert qu'à distribuer
des valeurs distinctes sur des lignes déjà existantes, la garde race-safe de
production reste `apps/ventes/utils/references.py` pour toute création
FUTURE). Idempotent : un document déjà pourvu d'une référence n'est jamais
retouché.
"""
from collections import defaultdict

from django.db import migrations


def backfill_references(apps, schema_editor):
    Document = apps.get_model('ged', 'Document')
    counters = defaultdict(int)
    qs = (Document.objects.filter(reference='')
          .order_by('company_id', 'created_at', 'id')
          .iterator(chunk_size=500))
    for doc in qs:
        company_id = doc.company_id
        if company_id is None:
            # Aucun document sans société en pratique (company posée côté
            # serveur à la création) ; on saute par prudence plutôt que de
            # générer une référence non scopée.
            continue
        created = doc.created_at
        period = created.strftime('%Y%m') if created else '000000'
        key = (company_id, period)
        counters[key] += 1
        doc.reference = f'DOC-{period}-{counters[key]:04d}'
        doc.save(update_fields=['reference'])


class Migration(migrations.Migration):

    dependencies = [
        ('ged', '0042_zged15_document_reference'),
    ]

    operations = [
        migrations.RunPython(backfill_references, migrations.RunPython.noop),
    ]
