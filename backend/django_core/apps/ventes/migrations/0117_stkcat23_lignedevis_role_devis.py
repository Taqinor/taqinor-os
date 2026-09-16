"""STKCAT23 — `LigneDevis.role_devis` : le rôle de la ligne, FIGÉ à sa création.

ADDITIF PUR : une colonne NULLABLE, sans défaut, SANS BACKFILL. Toute ligne
existante vaut NULL, et NULL veut dire « les mots-clés de la désignation
décident » — c'est-à-dire exactement le comportement d'hier. Le répartiteur
d'options du PDF (`quote_engine/builder._repartir_options`) et la table
d'icônes (`generate_devis_premium.icon_img`) lisent le rôle STOCKÉ d'abord et
gardent leurs mots-clés en REPLI PERMANENT : aucun devis existant ne change de
répartition, de total ni de nombre de pages.

Même contrat, même forme et même raison que `LigneDevis.variante` (L-2OPT) :
un champ qui DÉCLARE ce que le code devinait, sans jamais retirer la devinette.

Les `choices` sont recopiées LITTÉRALEMENT — une migration est de l'HISTOIRE
FIGÉE, elle doit rejouer à l'identique alors que `core.product_roles.ROLES_DEVIS`
est vivant. Un `choices` ne produit aucun DDL sur PostgreSQL : il vit dans
l'état Django, pas dans le schéma.

PAS D'INDEX ici, délibérément, à la différence de `stock.Produit.role_devis` :
une ligne de devis ne se cherche jamais PAR son rôle (elle se lit toujours par
son devis, qui est déjà indexé) — un index de plus sur la table la plus écrite
du module coûterait à chaque enregistrement de devis sans servir une requête.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0116_cht25_regulatory_dossier_prochaine_action'),
    ]

    operations = [
        migrations.AddField(
            model_name='lignedevis',
            name='role_devis',
            field=models.CharField(
                blank=True,
                choices=[
                    ('onduleur_reseau', 'onduleur_reseau'),
                    ('onduleur_hybride', 'onduleur_hybride'),
                    ('onduleur_offgrid', 'onduleur_offgrid'),
                    ('panneau', 'panneau'),
                    ('batterie', 'batterie'),
                    ('structure', 'structure'),
                    ('structure_acier', 'structure_acier'),
                    ('structure_alu', 'structure_alu'),
                    ('socle', 'socle'),
                    ('cable_dc', 'cable_dc'),
                    ('cable_terre', 'cable_terre'),
                    ('smart_meter', 'smart_meter'),
                    ('wifi_dongle', 'wifi_dongle'),
                    ('accessoires', 'accessoires'),
                    ('tableau', 'tableau'),
                    ('installation', 'installation'),
                    ('transport', 'transport'),
                    ('suivi', 'suivi'),
                ],
                help_text="Rôle de composition FIGÉ à la création de la "
                          "ligne. Vide = rôle non résolu : les mots-clés de la "
                          "désignation décident, comme avant.",
                max_length=32,
                null=True,
                verbose_name='Rôle de la ligne',
            ),
        ),
    ]
