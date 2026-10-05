"""CIQ103 — déclare le ``role_ci`` des articles C&I EXISTANTS, par leur code.

Migration de DONNÉES, gardée sur ``role_ci`` vide : un produit dont le rôle
C&I est déjà saisi n'est JAMAIS réécrit. Aucun prix et aucun nom n'est touché
(seule la colonne ``role_ci`` change).

Correspondance (codes du seeder ``seed_catalogue``) :
  * ``SMART-MET`` (Smart Meter Huawei) → ``compteur_injection``. Sa fiche
    ``lim_mode`` reste VIDE : la fiche seedée ne publie pas son mode de
    raccordement.

RÉVERSIBLE : le retour remet à vide le rôle des seules lignes qui portent
encore EXACTEMENT le rôle posé par cette migration, pour le SKU concerné.
"""
from django.db import migrations


ROLE_CI_PAR_SKU = {'SMART-MET': 'compteur_injection'}


def declarer_roles_ci(apps, schema_editor):
    Produit = apps.get_model('stock', 'Produit')
    for sku, role in ROLE_CI_PAR_SKU.items():
        # Gardé sur « rôle vide » : une saisie du fondateur n'est jamais écrasée.
        Produit.objects.filter(sku=sku, role_ci='').update(role_ci=role)


def retirer_roles_ci(apps, schema_editor):
    Produit = apps.get_model('stock', 'Produit')
    for sku, role in ROLE_CI_PAR_SKU.items():
        Produit.objects.filter(sku=sku, role_ci=role).update(role_ci='')


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0163_ciq101_produit_ci'),
    ]

    operations = [
        migrations.RunPython(declarer_roles_ci, retirer_roles_ci),
    ]
