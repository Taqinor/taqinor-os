"""ADEV86 — vocabulaire ``Produit.role_ci`` étendu (ADDITIF PUR).

ADEV86 (D-ACI-3=b) : le C&I s'ouvre au monophasé — rôle
``onduleur_string_mono`` AJOUTÉ en fin de ``core.product_roles.ROLES_CI``.

Seuls les ``choices`` du champ changent (aucune colonne, aucune donnée réécrite,
aucun produit reclassé) : ``AlterField`` sans effet SQL. RÉVERSIBLE : le retour
arrière revient à la liste de CIQ101 (0163).
"""
from django.db import migrations, models


ROLES_CI = [
    'onduleur_string_tri', 'compteur_injection', 'controleur_injection',
    'logger_supervision', 'structure_ci', 'cable_ac', 'protection_ac',
    'protection_dc', 'coffret_ac', 'coffret_dc', 'mise_a_la_terre',
    'cellule_mt', 'etudes_ingenierie', 'pose_structure', 'pose_modules',
    'raccordement_ac', 'mise_en_service', 'dossier_raccordement',
    'levage_acces', 'transport_ci', 'om_ci', 'batterie_ci',
    'onduleur_string_mono',
]


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0171_alter_imputationavoirfournisseur_avoir_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='produit',
            name='role_ci',
            field=models.CharField(
                blank=True, choices=[(r, r) for r in ROLES_CI], db_index=True,
                default='',
                help_text="Rôle DÉCLARÉ dans une composition commerciale/"
                          "industrielle (compteur_injection, structure_ci…). "
                          "Vide = non déclaré.",
                max_length=32, verbose_name='Rôle C&I'),
        ),
    ]
