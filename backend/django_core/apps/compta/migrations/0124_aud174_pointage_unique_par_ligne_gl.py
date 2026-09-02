"""AUD174 — un seul pointage par ligne du grand livre (rapprochement bancaire).

``PointageReleve`` n'imposait l'unicité que sur ``(ligne_releve, ligne_gl)`` :
rien n'empêchait un second pointage de la MÊME ``ligne_gl`` contre une autre
ligne de relevé, donc le même mouvement bancaire pouvait être déclaré
concordant dans deux rapprochements ouverts sur le même compte — masquant
l'anomalie réelle (relevé dupliqué, ligne bancaire manquante) exactement là où
le contrôle devait la révéler.

Deux opérations, dans cet ordre :

1. ``RunPython`` — purge les DOUBLONS préexistants, en gardant le pointage le
   PLUS ANCIEN de chaque ``ligne_gl`` (le premier rapprochement, légitime).
   Sans cette étape la contrainte échouerait au déploiement sur toute base
   portant déjà l'anomalie. L'inverse est un no-op : `git revert` retire la
   contrainte, et les lignes supprimées étaient précisément la corruption.
2. ``AddConstraint`` — l'unicité elle-même.
"""

from django.db import migrations, models


def _purger_doublons(apps, schema_editor):
    PointageReleve = apps.get_model('compta', 'PointageReleve')
    vus = set()
    a_supprimer = []
    for pk, ligne_gl_id in (PointageReleve.objects
                            .order_by('ligne_gl_id', 'id')
                            .values_list('id', 'ligne_gl_id')
                            .iterator()):
        if ligne_gl_id in vus:
            a_supprimer.append(pk)
        else:
            vus.add(ligne_gl_id)
    if a_supprimer:
        PointageReleve.objects.filter(id__in=a_supprimer).delete()


def _noop(apps, schema_editor):
    """Inverse : rien à restaurer (les lignes purgées étaient l'anomalie)."""


class Migration(migrations.Migration):

    dependencies = [
        ('compta', '0123_aud170_piste_audit_protect'),
    ]

    operations = [
        migrations.RunPython(_purger_doublons, _noop),
        migrations.AddConstraint(
            model_name='pointagereleve',
            constraint=models.UniqueConstraint(
                fields=('ligne_gl',),
                name='uniq_pointage_par_ligne_gl',
            ),
        ),
    ]
