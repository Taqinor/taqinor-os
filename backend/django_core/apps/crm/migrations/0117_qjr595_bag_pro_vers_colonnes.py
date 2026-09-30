"""QJR595 — rétro-remplissage : puissance souscrite (kVA) et surface de toiture
d'un client pro, restées dans ``web_questionnaire``, vers leurs colonnes.

DONNÉES seulement (aucun changement de schéma). Une colonne n'est remplie que
si elle est VIDE et que la bag porte la clé ; la bag n'est jamais modifiée.
``compteur_puissance_kva`` est borné à 99999.99 (max_digits=7). Jamais
``surface_m2`` (peut être au sol). Retour arrière : no-op.
"""
from decimal import Decimal, InvalidOperation

from django.db import migrations

LOT = 500
MAX_KVA = Decimal('99999.99')


def _dec(raw):
    if isinstance(raw, bool) or raw in (None, ''):
        return None
    try:
        val = Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return None
    return val if val.is_finite() and val >= 0 else None


def retro_remplir(apps, schema_editor):
    Lead = apps.get_model('crm', 'Lead')
    qs = Lead.objects.exclude(web_questionnaire=None).exclude(
        web_questionnaire={}).only(
        'pk', 'web_questionnaire', 'compteur_puissance_kva',
        'surface_toiture_m2').order_by('pk')
    pks = list(qs.values_list('pk', flat=True))
    for i in range(0, len(pks), LOT):
        for lead in Lead.objects.filter(pk__in=pks[i:i + LOT]):
            bag = lead.web_questionnaire
            if not isinstance(bag, dict):
                continue
            champs = []
            if lead.compteur_puissance_kva is None:
                kva = _dec(bag.get('puissance_kva'))
                if kva is not None and kva <= MAX_KVA:
                    lead.compteur_puissance_kva = kva
                    champs.append('compteur_puissance_kva')
            if lead.surface_toiture_m2 is None:
                surf = _dec(bag.get('surface_toiture_m2'))
                if surf is not None and surf < Decimal('100000000'):
                    lead.surface_toiture_m2 = surf
                    champs.append('surface_toiture_m2')
            if champs:
                lead.save(update_fields=champs)


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0116_cockpit_relance_etape_traces'),
    ]

    operations = [
        migrations.RunPython(retro_remplir, migrations.RunPython.noop),
    ]
