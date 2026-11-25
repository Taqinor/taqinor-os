"""D-ACAL-130 (fondateur 25/11/2026, « 540 DH TTC per panel ») — prix de la
structure au sol de pompage ``STR-SOL-PMP`` (quantité du kit = nombre de
panneaux), à 0 sur les bases existantes : la valeur de sa structure C&I lestée
(CI-STRUCT-PLAT-LEST).

540 DH TTC → 450,00 HT (``seed_catalogue.ht`` = TTC / 1,2 arrondi au centime) ;
valeur FIGÉE ici, jamais importée du code vivant. Depuis la garde D-ACAL-130,
un article de pompage n'est candidat ni au C&I (``stock.selectors.
_role_ci_par_fiche``) ni au résidentiel (``ventes.domain.catalogue.
est_article_pompage``) : ce prix ne sert que le kit de pompage.

Gardes : dans toute société, ``prix_vente`` reçoit le HT SEULEMENT là où il
vaut encore 0 (un prix saisi n'est jamais réécrit) ; rien d'autre ; aucun
article créé ; idempotente ; mises à jour par lots de clés primaires. Le retour
remet à 0 les seules lignes qui portent encore EXACTEMENT le HT écrit ici.
"""
from decimal import Decimal

from django.db import migrations

#: SKU → prix de vente HT (540 TTC par panneau).
PRIX_HT = {
    'STR-SOL-PMP': Decimal('450.00'),
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
        ('stock', '0195_dacal130_bareme_installation_pompage'),
    ]

    operations = [
        migrations.RunPython(poser_prix, retirer_prix),
    ]
