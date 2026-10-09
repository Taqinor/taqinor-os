# APDF40 — rattrapage des nomenclatures déjà gelées : chaque ligne de
# `Installation.bom` reçoit une clé `nature` (`service` | `materiel`) lue du
# type de la catégorie du produit. Données seulement, revertable (noop : la
# clé ajoutée est inoffensive pour les lecteurs). Quantités inchangées.

from django.db import migrations


def nature_pour_ligne(ligne, types_par_produit):
    if ligne.get('nature') in ('service', 'materiel'):
        return ligne['nature']
    type_cat = types_par_produit.get(ligne.get('produit_id'))
    return 'service' if type_cat == 'service' else 'materiel'


def rattraper_nature(apps, schema_editor):
    Installation = apps.get_model('installations', 'Installation')
    Produit = apps.get_model('stock', 'Produit')
    qs = Installation.objects.exclude(bom__isnull=True)
    for pk in qs.values_list('pk', flat=True).iterator(chunk_size=200):
        inst = Installation.objects.get(pk=pk)
        bom = inst.bom
        if not isinstance(bom, list) or not bom:
            continue
        ids = {ligne.get('produit_id') for ligne in bom
               if isinstance(ligne, dict) and ligne.get('produit_id')}
        types = dict(Produit.objects.filter(pk__in=ids).values_list(
            'pk', 'categorie__type_equipement'))
        neuf = []
        change = False
        for ligne in bom:
            if isinstance(ligne, dict) and 'nature' not in ligne:
                ligne = dict(ligne, nature=nature_pour_ligne(ligne, types))
                change = True
            neuf.append(ligne)
        if change:
            Installation.objects.filter(pk=pk).update(bom=neuf)


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0128_acht36_cloturee_notifiee_le'),
        ('stock', '0168_astk192_rdv_fournisseur_bcf'),
    ]

    operations = [
        migrations.RunPython(rattraper_nature, migrations.RunPython.noop),
    ]
