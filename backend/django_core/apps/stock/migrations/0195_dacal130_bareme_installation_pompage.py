"""D-ACAL-130 (fondateur 25/11/2026, « 2 000 + 250 per panel HT ») — barème de
la pose de pompage ``INST-PMP`` : celui de l'installation résidentielle.

Le kit de pompage chiffre ``INST-PMP`` par son barème seul
(``core.pompage.kit.bareme_saisi`` : ``prix_fixe_ht`` / ``prix_par_panneau_ht``
> 0) ; ``prix_vente`` n'est pas touché (il reste 0, ce qui garde l'article hors
du devis résidentiel). Valeurs FIGÉES ici, jamais importées du seeder.

Gardes : dans toute société, CHAQUE champ du barème n'est écrit que s'il est
vide ou à 0 (un barème saisi n'est jamais réécrit) ; rien d'autre (ni
``prix_vente``, ni ``prix_achat``, ni nom) ; aucun article créé ; idempotente.
Le retour vide les seuls champs qui portent encore EXACTEMENT la valeur écrite.
"""
from decimal import Decimal

from django.db import migrations
from django.db.models import Q

#: SKU → champs du barème (DH HT).
BAREMES = {
    'INST-PMP': {'prix_fixe_ht': Decimal('2000'),
                 'prix_par_panneau_ht': Decimal('250')},
}


def poser_bareme(apps, schema_editor):
    Produit = apps.get_model('stock', 'Produit')
    for sku, champs in BAREMES.items():
        for champ, valeur in champs.items():
            Produit.objects.filter(sku=sku).filter(
                Q(**{champ: None}) | Q(**{champ: 0})).update(**{champ: valeur})


def retirer_bareme(apps, schema_editor):
    Produit = apps.get_model('stock', 'Produit')
    for sku, champs in BAREMES.items():
        for champ, valeur in champs.items():
            Produit.objects.filter(sku=sku, **{champ: valeur}).update(
                **{champ: None})


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0194_dacal129_tension_cv_petites_pompes'),
    ]

    operations = [
        migrations.RunPython(poser_bareme, retirer_bareme),
    ]
