# STKCAT21 (16/09/2026) — ajout de `Produit.role_devis` : le RÔLE DÉCLARÉ d'un
# produit dans une composition de devis (panneau, batterie, structure…).
#
# ADDITIF PUR : colonne NULLABLE, sans défaut, SANS BACKFILL. Tout produit
# existant vaut NULL, donc la résolution du rôle retombe exactement sur le
# comportement d'aujourd'hui (famille de la catégorie puis mots-clés du nom —
# cf. `core.product_roles.role_effectif`). Aucune donnée n'est touchée, aucun
# comportement ne change tant qu'un rôle n'est pas déclaré à la main.
#
# LES `choices` SONT RECOPIÉES LITTÉRALEMENT ICI, et c'est délibéré : une
# migration est de l'HISTOIRE FIGÉE (elle doit rejouer à l'identique dans dix
# ans), alors que `core.product_roles.ROLES_DEVIS` est vivant. C'est la même
# raison que la copie figée de la table de STKCAT4 (migration 0146). Un
# `choices` ne produit d'ailleurs AUCUN DDL sur PostgreSQL : il vit dans l'état
# Django, pas dans le schéma — ajouter un rôle plus tard ne touchera pas cette
# colonne.
#
# L'INDEX est posé par `db_index=True` dans le même `AddField` (Django nomme
# l'index lui-même — on ne lui impose jamais un nom écrit à la main, qui
# divergerait du nom haché attendu). Ce n'est pas un `AddIndex` sur une table
# vivante : `stock_produit` est une table de CATALOGUE (quelques centaines de
# lignes par société), et la garde `scripts/check_safe_migrations.py` ne
# concerne que les `AddIndex` d'opération.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0146_stkcat4_typer_categories_existantes'),
    ]

    operations = [
        migrations.AddField(
            model_name='produit',
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
                db_index=True,
                help_text="Rôle DÉCLARÉ du produit dans une composition de "
                          "devis (panneau, batterie, structure…). Vide = non "
                          "déclaré : le rôle est alors déduit de la catégorie "
                          "puis des mots-clés du nom, comme avant.",
                max_length=32,
                null=True,
                verbose_name='Rôle sur un devis',
            ),
        ),
    ]
