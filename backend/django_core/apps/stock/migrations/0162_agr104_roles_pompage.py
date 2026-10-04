"""AGR104 — déclare le ``role_pompage`` des SKU pompage EXISTANTS, par leur code.

Migration de DONNÉES, gardée sur ``role_pompage`` vide : un produit dont le
rôle est déjà saisi n'est JAMAIS réécrit. Aucun prix et aucun nom n'est touché
(seule la colonne ``role_pompage`` change).

Correspondance (codes du seeder ``seed_catalogue``) :
  * pompes génériques ``PMP-IMM-*`` / ``PMP-SUR-*`` et OSP ``PMP-OSP-30-*``
    → ``pompe`` ;
  * variateurs ``VEI-SI2x-*`` → ``variateur_pompage`` ; l'afficheur
    ``VEI-SI22-AFF`` → ``afficheur_variateur`` ;
  * câbles solaires DC ``CAB-6MM-M`` et ``CAB-H1Z2Z2-*-M`` → ``cable_dc`` ;
  * protections DC du lot PVG3 (fusibles gPV, porte-fusible, parafoudre DC,
    sectionneur DC, coffret DC) → ``protection_dc``. Les protections AC
    (disjoncteurs, différentiels, parafoudre AC, coffret AC) ne sont PAS
    déclarées : aucun rôle pompage AC n'existe, on préfère l'omission au faux
    positif.

RÉVERSIBLE : le retour remet à vide le rôle des seules lignes qui portent
encore EXACTEMENT le rôle posé par cette migration, pour le SKU concerné.
"""
from django.db import migrations


_POMPES = (
    ['PMP-IMM-1.5M', 'PMP-IMM-3M', 'PMP-IMM-4T', 'PMP-IMM-5.5T',
     'PMP-IMM-7.5T', 'PMP-IMM-10T', 'PMP-SUR-1.5M', 'PMP-SUR-3T']
    + ['PMP-OSP-30-8', 'PMP-OSP-30-11', 'PMP-OSP-30-13', 'PMP-OSP-30-15',
       'PMP-OSP-30-16', 'PMP-OSP-30-17', 'PMP-OSP-30-20', 'PMP-OSP-30-21',
       'PMP-OSP-30-25', 'PMP-OSP-30-26', 'PMP-OSP-30-35']
)
_VARIATEURS = [
    'VEI-SI22-2.2-220', 'VEI-SI23-2.2-220', 'VEI-SI23-2.2-380',
    'VEI-SI23-4-380', 'VEI-SI23-5.5-380', 'VEI-SI23-7.5-380',
    'VEI-SI23-11-380', 'VEI-SI23-15-380', 'VEI-SI23-18-380',
    'VEI-SI23-22-380', 'VEI-SI23-30-380', 'VEI-SI23-37-380',
    'VEI-SI23-45-380', 'VEI-SI23-55-380', 'VEI-SI23-75-380',
]
_CABLES_DC = ['CAB-6MM-M', 'CAB-H1Z2Z2-4-M', 'CAB-H1Z2Z2-6-M',
              'CAB-H1Z2Z2-10-M', 'CAB-H1Z2Z2-16-M']
_PROTECTIONS_DC = [
    'FUS-GPV-1000-15A', 'FUS-GPV-1000-20A', 'PF-1000', 'PARA-DC-T2-1000',
    'SECT-DC-1000-25A', 'COF-DC-2STR',
]

ROLE_PAR_SKU = {}
ROLE_PAR_SKU.update({sku: 'pompe' for sku in _POMPES})
ROLE_PAR_SKU.update({sku: 'variateur_pompage' for sku in _VARIATEURS})
ROLE_PAR_SKU['VEI-SI22-AFF'] = 'afficheur_variateur'
ROLE_PAR_SKU.update({sku: 'cable_dc' for sku in _CABLES_DC})
ROLE_PAR_SKU.update({sku: 'protection_dc' for sku in _PROTECTIONS_DC})


def declarer_roles(apps, schema_editor):
    Produit = apps.get_model('stock', 'Produit')
    for sku, role in ROLE_PAR_SKU.items():
        # Gardé sur « rôle vide » : une saisie du fondateur n'est jamais écrasée.
        Produit.objects.filter(sku=sku, role_pompage='').update(
            role_pompage=role)


def retirer_roles(apps, schema_editor):
    Produit = apps.get_model('stock', 'Produit')
    for sku, role in ROLE_PAR_SKU.items():
        Produit.objects.filter(sku=sku, role_pompage=role).update(
            role_pompage='')


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0161_agr101_fiche_pompage'),
    ]

    operations = [
        migrations.RunPython(declarer_roles, retirer_roles),
    ]
