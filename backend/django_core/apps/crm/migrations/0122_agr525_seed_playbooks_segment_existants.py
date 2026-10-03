"""AGR525 — rattrapage des playbooks de segment (CAD125) sur les sociétés
EXISTANTES + condition FDA réservée à la pompe au butane.

DONNÉES seulement, sur modèles HISTORIQUES. Les constantes de
``services.PLAYBOOKS_SEGMENT_CAD125`` sont RECOPIÉES ici (une migration ne
change jamais de sens quand le code évolue). Pour chaque société :

* les deux playbooks sont créés s'ils manquent (étape « prise de contact »
  de STAGES.py + leur tâche unique) ;
* un playbook FDA dont la condition est EXACTEMENT l'ancienne condition CAD125
  passe à la nouvelle (agricole ET pompe au butane) ;
* un playbook personnalisé (condition différente) n'est JAMAIS réécrit — le
  cas est journalisé ;
* les progressions existantes ne sont jamais supprimées.

Idempotente ; retour arrière : no-op.
"""
import logging

from django.db import migrations

from apps.crm import stages

logger = logging.getLogger(__name__)

NOM_8221 = 'Segment — dossier d’autoproduction 82-21'
NOM_FDA = 'Segment — dossier de subvention agricole (FDA)'

CONDITION_8221 = {
    'op': 'or',
    'conditions': [
        {'field': 'type_installation', 'operator': 'eq',
         'value': 'industriel'},
        {'field': 'type_installation', 'operator': 'eq',
         'value': 'commercial'},
    ],
}
ANCIENNE_CONDITION_FDA = {
    'op': 'or',
    'conditions': [
        {'field': 'type_installation', 'operator': 'eq', 'value': 'agricole'},
    ],
}
NOUVELLE_CONDITION_FDA = {
    'op': 'and',
    'conditions': [
        {'field': 'type_installation', 'operator': 'eq', 'value': 'agricole'},
        {'field': 'pompe_alim_actuelle', 'operator': 'eq',
         'value': 'butane'},
    ],
}

PLAYBOOKS = (
    (NOM_8221, CONDITION_8221,
     'Demander où en est le dossier d’autoproduction 82-21 '
     '(texte « dossier_8221 » au catalogue des messages)'),
    (NOM_FDA, NOUVELLE_CONDITION_FDA,
     'Demander où en est le dossier de subvention agricole FDA '
     '(texte « dossier_fda » au catalogue des messages)'),
)


def rattraper(apps, schema_editor):
    Company = apps.get_model('authentication', 'Company')
    Playbook = apps.get_model('crm', 'Playbook')
    PlaybookEtape = apps.get_model('crm', 'PlaybookEtape')
    PlaybookTache = apps.get_model('crm', 'PlaybookTache')
    for company in Company.objects.all().order_by('pk'):
        for nom, condition, tache in PLAYBOOKS:
            playbook = Playbook.objects.filter(
                company=company, nom=nom).order_by('pk').first()
            if playbook is None:
                playbook = Playbook.objects.create(
                    company=company, nom=nom, actif=True,
                    condition=condition)
                etape, _ = PlaybookEtape.objects.get_or_create(
                    playbook=playbook, stage=stages.CONTACTED,
                    defaults={'ordre': 0})
                PlaybookTache.objects.get_or_create(
                    etape=etape, libelle=tache,
                    defaults={'obligatoire': False, 'ordre': 0})
                continue
            if nom != NOM_FDA or playbook.condition == condition:
                continue
            if playbook.condition == ANCIENNE_CONDITION_FDA:
                playbook.condition = NOUVELLE_CONDITION_FDA
                playbook.save(update_fields=['condition'])
            else:
                logger.info(
                    'AGR525 : playbook FDA personnalisé laissé intact '
                    '(société #%s, playbook #%s).', company.pk, playbook.pk)


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0121_agr522_lead_dossier_subvention'),
    ]

    operations = [
        migrations.RunPython(rattraper, migrations.RunPython.noop),
    ]
