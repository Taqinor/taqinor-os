"""Backfill du modèle Marque depuis les valeurs distinctes Produit.marque.

Additif : le texte `Produit.marque` reste intact ; on crée une Marque par
valeur distincte (scopée société) et on relie `Produit.marque_ref`. Rien
n'est supprimé ni altéré.
"""
from django.db import migrations


def backfill(apps, schema_editor):
    Produit = apps.get_model('stock', 'Produit')
    Marque = apps.get_model('stock', 'Marque')

    # (company_id, nom normalisé) déjà couples présents → crée la Marque, puis
    # relie chaque produit.
    qs = (
        Produit.objects
        .exclude(marque__isnull=True).exclude(marque='')
    )
    cache = {}
    for prod in qs.iterator():
        nom = (prod.marque or '').strip()
        if not nom:
            continue
        cache_key = (prod.company_id, nom)
        marque = cache.get(cache_key)
        if marque is None:
            marque, _ = Marque.objects.get_or_create(
                company_id=prod.company_id, nom=nom)
            cache[cache_key] = marque
        if prod.marque_ref_id != marque.id:
            prod.marque_ref = marque
            prod.save(update_fields=['marque_ref'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0015_marque_produit_marque_ref'),
    ]

    operations = [
        migrations.RunPython(backfill, noop),
    ]
