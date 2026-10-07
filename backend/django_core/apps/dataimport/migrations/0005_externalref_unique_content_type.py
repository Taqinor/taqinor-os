# AANA10 — la référence externe d'import inclut le TYPE de contenu.
#
# Avant : UNIQUE (company, external_system, external_id) — une référence « A1 »
# posée sur un lead était retrouvée par l'import CLIENTS et appliquée au client
# de même pk. Après : UNIQUE (company, external_system, content_type,
# external_id).
#
# Sens avant : contrainte ÉLARGIE — toute ligne existante, déjà unique sur le
# triplet, l'est a fortiori sur le quadruplet : aucune donnée à corriger. On
# ajoute la nouvelle contrainte AVANT de retirer l'ancienne (jamais de fenêtre
# sans unicité).
#
# Sens arrière (revert) : des références de types différents peuvent alors
# partager le même id externe et violeraient l'ancienne contrainte. Le
# ``RunPython`` inverse ne garde que la plus ANCIENNE référence de chaque
# triplet (les autres sont des liens techniques, jamais une donnée métier)
# avant de rétablir l'ancienne contrainte.
from django.db import migrations, models


def _dedoublonner_pour_revert(apps, schema_editor):
    ExternalRef = apps.get_model('dataimport', 'ExternalRef')
    vus = set()
    a_supprimer = []
    for ref in ExternalRef.objects.order_by('pk').values_list(
            'pk', 'company_id', 'external_system', 'external_id'):
        cle = ref[1:]
        if cle in vus:
            a_supprimer.append(ref[0])
        else:
            vus.add(cle)
    if a_supprimer:
        ExternalRef.objects.filter(pk__in=a_supprimer).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('dataimport', '0004_importjob_ecraser_importjobrow_modifications'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='externalref',
            constraint=models.UniqueConstraint(
                fields=('company', 'external_system', 'content_type',
                        'external_id'),
                name='uniq_dataimport_external_ref_ct'),
        ),
        migrations.RemoveConstraint(
            model_name='externalref',
            name='uniq_dataimport_external_ref',
        ),
        migrations.RunPython(
            migrations.RunPython.noop, _dedoublonner_pour_revert),
    ]
