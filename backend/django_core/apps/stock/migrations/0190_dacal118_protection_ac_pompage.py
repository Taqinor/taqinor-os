"""D-ACAL-118 (fondateur 25/11/2026, « DC box + AC protection ») — le kit
minimum des NOUVEAUX devis de pompage porte un disjoncteur AC et un parafoudre
AC entre le variateur et la pompe : nouveau rôle pompage ``protection_ac``.

Deux opérations, additives et RÉVERSIBLES :

* ``AlterField`` des ``choices`` de ``Produit.role_pompage`` (aucun effet SQL) ;
* migration de DONNÉES gardée sur « rôle vide » (même patron que 0162) : les
  disjoncteurs AC et le parafoudre AC du lot PVG3 du seeder reçoivent
  ``protection_ac``. Un rôle déjà saisi n'est JAMAIS réécrit ; aucun prix,
  aucun nom, aucune quantité n'est touché (seule la colonne ``role_pompage``).
  Les différentiels et le coffret AC restent sans rôle pompage (hors décision).

Le retour remet à vide le rôle des seules lignes qui portent encore EXACTEMENT
``protection_ac`` pour le SKU concerné.
"""
from django.db import migrations, models

#: Vocabulaire ``ROLES_POMPAGE`` FIGÉ à cette migration (celui de 0160 +
#: ``protection_ac``) — jamais importé du code vivant.
ROLES = [
    'pompe', 'variateur_pompage', 'afficheur_variateur', 'structure_sol',
    'cable_dc', 'cable_descente', 'protection_dc', 'sonde_niveau',
    'compteur_eau', 'colonne_refoulement', 'clapet', 'tuyauterie', 'bassin',
    'installation_pompage', 'entretien_pompage', 'antivol', 'cloture',
    'protection_ac',
]

#: Codes du seeder (``seed_catalogue.CABLES_PROTECTIONS_VIDES``).
SKUS_PROTECTION_AC = [
    'DISJ-AC-C-16-1P', 'DISJ-AC-C-20-1P', 'DISJ-AC-C-25-1P',
    'DISJ-AC-C-32-1P', 'DISJ-AC-C-16-4P', 'DISJ-AC-C-20-4P',
    'DISJ-AC-C-25-4P', 'DISJ-AC-C-32-4P', 'PARA-AC-T2',
]


def declarer_roles(apps, schema_editor):
    Produit = apps.get_model('stock', 'Produit')
    Produit.objects.filter(sku__in=SKUS_PROTECTION_AC, role_pompage='').update(
        role_pompage='protection_ac')


def retirer_roles(apps, schema_editor):
    Produit = apps.get_model('stock', 'Produit')
    Produit.objects.filter(sku__in=SKUS_PROTECTION_AC,
                           role_pompage='protection_ac').update(role_pompage='')


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0189_hybride_80kw_et_prix_batterie_ht'),
    ]

    operations = [
        migrations.AlterField(
            model_name='produit',
            name='role_pompage',
            field=models.CharField(
                blank=True, db_index=True, default='',
                choices=[(r, r) for r in ROLES],
                help_text="Rôle DÉCLARÉ dans une composition pompage (pompe, "
                          "variateur_pompage, sonde_niveau…). Vide = non "
                          "déclaré.",
                max_length=32, verbose_name='Rôle pompage'),
        ),
        migrations.RunPython(declarer_roles, retirer_roles),
    ]
