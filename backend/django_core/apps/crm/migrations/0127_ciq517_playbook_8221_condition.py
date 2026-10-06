"""CIQ517 (D-CIQ-6) — le playbook « dossier 82-21 » (CAD125) ne vise plus que
les sites MT, les leads en régularisation 82-21 et les clients qui veulent
revendre ; sa tâche parle du « raccordement et des autorisations du site ».

DONNÉES seulement, sur modèles HISTORIQUES. Les constantes sont RECOPIÉES ici
(une migration ne change jamais de sens quand le code évolue) :

* un playbook 82-21 dont la condition est EXACTEMENT celle de CAD125 (tout
  commercial ou industriel) passe à la nouvelle condition ;
* sa tâche dont le libellé est EXACTEMENT l'ancien est alignée ;
* un playbook PERSONNALISÉ (condition différente) n'est JAMAIS réécrit — le
  cas est journalisé ;
* aucune progression n'est créée ni supprimée, aucun devis touché (D-CIQ-21).

Idempotente (rejouée : plus rien ne correspond à l'ancienne condition) ;
retour arrière : no-op.
"""
import logging

from django.db import migrations

logger = logging.getLogger(__name__)

NOM_8221 = 'Segment — dossier d’autoproduction 82-21'

ANCIENNE_CONDITION_8221 = {
    'op': 'or',
    'conditions': [
        {'field': 'type_installation', 'operator': 'eq',
         'value': 'industriel'},
        {'field': 'type_installation', 'operator': 'eq',
         'value': 'commercial'},
    ],
}
NOUVELLE_CONDITION_8221 = {
    'op': 'and',
    'conditions': [
        ANCIENNE_CONDITION_8221,
        {'op': 'or', 'conditions': [
            {'field': 'tension_raccordement', 'operator': 'eq',
             'value': 'mt'},
            {'field': 'regularisation_8221', 'operator': 'eq',
             'value': True},
            {'field': 'objectif_projet', 'operator': 'eq',
             'value': 'injection_8221'},
        ]},
    ],
}
ANCIENNE_TACHE = ('Demander où en est le dossier d’autoproduction 82-21 '
                  '(texte « dossier_8221 » au catalogue des messages)')
NOUVELLE_TACHE = ('Demander où en sont le raccordement et les autorisations '
                  'du site (texte « dossier_8221 » au catalogue des '
                  'messages)')


def restreindre(apps, schema_editor):
    Playbook = apps.get_model('crm', 'Playbook')
    PlaybookTache = apps.get_model('crm', 'PlaybookTache')
    for playbook in Playbook.objects.filter(nom=NOM_8221).order_by('pk'):
        if playbook.condition == NOUVELLE_CONDITION_8221:
            continue
        if playbook.condition != ANCIENNE_CONDITION_8221:
            logger.info(
                'CIQ517 : playbook 82-21 personnalisé laissé intact '
                '(société #%s, playbook #%s).',
                playbook.company_id, playbook.pk)
            continue
        playbook.condition = NOUVELLE_CONDITION_8221
        playbook.save(update_fields=['condition'])
        for tache in PlaybookTache.objects.filter(
                etape__playbook=playbook, libelle=ANCIENNE_TACHE).iterator():
            tache.libelle = NOUVELLE_TACHE
            tache.save(update_fields=['libelle'])


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0126_ciq408_tranche_meta_ouverte'),
    ]

    operations = [
        migrations.RunPython(restreindre, migrations.RunPython.noop),
    ]
