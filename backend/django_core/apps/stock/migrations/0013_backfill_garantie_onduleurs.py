"""Garantie de deux onduleurs nommés — remplissage des champs vides uniquement.

Migration de DONNÉES (aucun changement de schéma). Le fondateur a fixé la
garantie équipement de deux onduleurs identifiés par leur nom exact
(insensible à la casse). On ne touche QUE garantie_mois, et SEULEMENT là où
il est encore vide (jamais d'écrasement, aucune suppression).

  - « Onduleur réseau 10kW »  → garantie_mois = 120
  - « Onduleur hybride 5kW »  → garantie_mois = 120

« Micro-onduleur 800W » est VOLONTAIREMENT exclu (laissé sans garantie sur
décision du fondateur). garantie_production_mois (panneaux) n'est pas touché.
Sens inverse = no-op (on ne peut pas savoir lesquels étaient vides avant).
"""
from django.db import migrations

GARANTIE = {
    'Onduleur réseau 10kW': 120,
    'Onduleur hybride 5kW': 120,
}


def backfill(apps, schema_editor):
    Produit = apps.get_model('stock', 'Produit')
    for nom, mois in GARANTIE.items():
        # iexact : match du nom exact, insensible à la casse, toutes sociétés.
        # __isnull=True : on ne remplit que le vide, jamais d'écrasement.
        Produit.objects.filter(nom__iexact=nom, garantie_mois__isnull=True).update(
            garantie_mois=mois)


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0012_backfill_garanties'),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
