"""VTA5 — les liens de notification ``/crm/visites/<id>`` deviennent
``/visites/<id>``.

L'app Visites est sortie du CRM et sa route d'écran a changé. Les
notifications DÉJÀ PERSISTÉES gardent, elles, l'ancien chemin : la cloche
mènerait à un écran mort pour tout feu vert ou renvoi notifié avant le
déploiement. On réécrit donc le préfixe en base.

Prudences :
* ciblage ÉTROIT — uniquement les liens qui COMMENCENT par ``/crm/visites/``
  (jamais une substitution au milieu d'une URL) ;
* IDEMPOTENTE — un lien déjà en ``/visites/`` n'est pas touché, et relancer la
  migration ne change rien ;
* RÉVERSIBLE — l'inverse repointe ``/visites/`` sur ``/crm/visites/`` ;
* écriture ligne à ligne avec ``update_fields``, sur le SEUL sous-ensemble
  concerné (``startswith``), jamais un UPDATE global de la table.
"""
from django.db import migrations

ANCIEN = '/crm/visites/'
NOUVEAU = '/visites/'


def _reecrire(apps, depuis, vers):
    Notification = apps.get_model('notifications', 'Notification')
    lignes = Notification.objects.filter(link__startswith=depuis)
    for notification in lignes.iterator():
        lien = notification.link or ''
        if not lien.startswith(depuis):
            continue
        notification.link = vers + lien[len(depuis):]
        notification.save(update_fields=['link'])


def vers_app_visites(apps, schema_editor):
    _reecrire(apps, ANCIEN, NOUVEAU)


def retour_vers_crm(apps, schema_editor):
    _reecrire(apps, NOUVEAU, ANCIEN)


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0052_eventtype_bilan_hebdo'),
    ]

    operations = [
        migrations.RunPython(vers_app_visites, retour_vers_crm),
    ]
