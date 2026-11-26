"""D-ACAL-127 (fondateur 25/11/2026) — prix PUBLICS confirmés de neuf articles
du kit minimum de pompage (lot PVG3 du seeder), à 0 sur les bases existantes.

Prix TTC lus sur mrelec.ma le 25/11/2026 (prix boutique, sans marge ajoutée),
stockés HT comme tout le catalogue (``prix_vente`` HT, TVA 20 % :
``seed_catalogue.ht`` = TTC / 1,2 arrondi au centime). Table FIGÉE ici — jamais
importée du code vivant.

Migration de DONNÉES additive, idempotente et RÉVERSIBLE :

* pour chaque SKU, dans toute société qui a l'article, ``prix_vente`` reçoit le
  HT SEULEMENT là où il vaut encore 0 — un article déjà chiffré à la main n'est
  JAMAIS réécrit ; aucun article n'est créé ;
* rien d'autre n'est touché : ni ``prix_achat`` (aucun prix d'achat donné), ni
  le nom, ni les quantités, ni ``PARA-AC-T2`` (aucun prix fiable : reste à 0).

Le retour remet à 0 les seules lignes qui portent encore EXACTEMENT le HT écrit
ici pour leur SKU (même patron que 0190).
"""
from decimal import Decimal

from django.db import migrations

#: SKU → prix de vente HT (TTC lu le 25/11/2026 en commentaire).
PRIX_HT = {
    'DISJ-AC-C-16-1P': Decimal('66.67'),    # 80 TTC — EATON Xpole AC 2P
    'DISJ-AC-C-20-1P': Decimal('66.67'),    # 80 TTC
    'DISJ-AC-C-25-1P': Decimal('66.67'),    # 80 TTC
    'DISJ-AC-C-32-1P': Decimal('69.17'),    # 83 TTC
    'DISJ-AC-C-16-4P': Decimal('106.67'),   # 128 TTC — CHINT NXB-63 4P
    'DISJ-AC-C-20-4P': Decimal('110.00'),   # 132 TTC
    'DISJ-AC-C-25-4P': Decimal('113.33'),   # 136 TTC
    'DISJ-AC-C-32-4P': Decimal('117.50'),   # 141 TTC
    'COF-DC-2STR': Decimal('1666.67'),      # 2 000 TTC — boîte de jonction DC
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
        ('stock', '0190_dacal118_protection_ac_pompage'),
    ]

    operations = [
        migrations.RunPython(poser_prix, retirer_prix),
    ]
