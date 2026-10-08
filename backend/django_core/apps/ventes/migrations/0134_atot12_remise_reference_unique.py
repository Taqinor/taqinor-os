"""ATOT12 — ``UniqueConstraint(company, reference)`` sur
``RemiseEncaissement`` (référence vide hors contrainte).

1. DÉDOUBLONNAGE d'abord (RunPython réversible) : pour chaque couple
   (société, référence) porté par plusieurs remises, la plus ANCIENNE garde
   son numéro ; les plus récentes reçoivent le prochain numéro libre du même
   préfixe (``REM-AAAAMM-`` + compteur), journalisé (logger
   ``apps.ventes.migrations``). Le retour arrière ne renumérote rien
   (no-op) : la contrainte est simplement retirée.
2. La contrainte, ensuite : le retry de ``create_with_reference`` peut enfin
   jouer sur une course.
"""
import logging
import re

from django.db import migrations, models

logger = logging.getLogger('apps.ventes.migrations')
_SUFFIXE = re.compile(r'^(?P<prefixe>.*?)(?P<num>\d+)$')


def dedoublonner(apps, schema_editor):
    Remise = apps.get_model('ventes', 'RemiseEncaissement')
    from django.db.models import Count
    doublons = (Remise.objects.exclude(reference='')
                .values('company_id', 'reference')
                .annotate(n=Count('id')).filter(n__gt=1))
    for groupe in doublons:
        rows = list(Remise.objects.filter(
            company_id=groupe['company_id'],
            reference=groupe['reference']).order_by('id'))
        for remise in rows[1:]:
            m = _SUFFIXE.match(remise.reference)
            if m:
                prefixe, largeur = m.group('prefixe'), len(m.group('num'))
                existants = Remise.objects.filter(
                    company_id=remise.company_id,
                    reference__startswith=prefixe).values_list(
                        'reference', flat=True)
                nums = [int(r[len(prefixe):]) for r in existants
                        if r[len(prefixe):].isdigit()]
                nouveau = f'{prefixe}{max(nums) + 1:0{largeur}d}'
            else:
                nouveau = f'{remise.reference}-{remise.pk}'[:50]
            logger.warning(
                'ATOT12 : remise #%s (société %s) renumérotée %s -> %s',
                remise.pk, remise.company_id, remise.reference, nouveau)
            remise.reference = nouveau
            remise.save(update_fields=['reference'])


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0133_atot6_notedebit_ventilation_tva'),
    ]

    operations = [
        migrations.RunPython(dedoublonner, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='remiseencaissement',
            constraint=models.UniqueConstraint(
                condition=models.Q(('reference', ''), _negated=True),
                fields=('company', 'reference'),
                name='uniq_remiseencaissement_reference_par_societe'),
        ),
    ]
