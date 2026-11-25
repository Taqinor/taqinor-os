"""D-ACAL-128 (fondateur 25/11/2026, « use 1000 ») — prix du parafoudre AC
``PARA-AC-T2`` du kit minimum de pompage, à 0 sur les bases existantes.

1 000 DH TTC, prix donné par le fondateur le 25/11/2026 (aucune annonce
marocaine fiable lue), stocké HT comme tout le catalogue (``seed_catalogue.ht``
= TTC / 1,2 arrondi au centime). Valeur FIGÉE ici — jamais importée du code
vivant. Mêmes gardes que 0191 : dans toute société, ``prix_vente`` reçoit le HT
SEULEMENT là où il vaut encore 0 (un prix saisi n'est jamais réécrit) ; rien
d'autre n'est touché (ni ``prix_achat``, ni nom, ni quantité) ; aucun article
créé ; idempotente. Le retour remet à 0 les seules lignes qui portent encore
EXACTEMENT le HT écrit ici.
"""
from decimal import Decimal

from django.db import migrations

#: SKU → prix de vente HT (1 000 TTC).
PRIX_HT = {
    'PARA-AC-T2': Decimal('833.33'),
}


#: Mise à jour par lots de clés primaires (garde check_safe_migrations) : jamais
#: un seul UPDATE global sur la table des produits.
TAILLE_BATCH = 500


def _update_par_batch(qs, **valeurs):
    pks = list(qs.values_list('pk', flat=True).order_by('pk'))
    for debut in range(0, len(pks), TAILLE_BATCH):
        batch = pks[debut:debut + TAILLE_BATCH]
        qs.model.objects.filter(pk__in=batch).update(**valeurs)


def poser_prix(apps, schema_editor):
    Produit = apps.get_model('stock', 'Produit')
    for sku, prix in PRIX_HT.items():
        _update_par_batch(Produit.objects.filter(sku=sku, prix_vente=0), prix_vente=prix)


def retirer_prix(apps, schema_editor):
    Produit = apps.get_model('stock', 'Produit')
    for sku, prix in PRIX_HT.items():
        _update_par_batch(Produit.objects.filter(sku=sku, prix_vente=prix),
                          prix_vente=Decimal('0'))


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0191_dacal127_prix_protections_pompage'),
    ]

    operations = [
        migrations.RunPython(poser_prix, retirer_prix),
    ]
