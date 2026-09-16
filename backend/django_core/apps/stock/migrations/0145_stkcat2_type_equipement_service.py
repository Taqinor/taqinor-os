# STKCAT2 (16/09/2026) — ajout de la valeur SERVICE à
# `Categorie.TypeEquipement`. Additif PUR : une seule valeur de plus EN FIN de
# liste de choix, aucune valeur existante renommée ni retirée, aucune donnée
# touchée (un `AlterField(choices=...)` ne produit aucun DDL sur PostgreSQL —
# les choices vivent dans l'état Django, pas dans le schéma).
#
# Pourquoi : une catégorie « Services & prestations » (installation,
# transport, suivi journalier) n'est pas un équipement ; sans valeur honnête
# elle restait NULL, donc indistinguable d'une catégorie simplement non typée.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0144_ntp2p21_frais_livraison_estimes'),
    ]

    operations = [
        migrations.AlterField(
            model_name='categorie',
            name='type_equipement',
            field=models.CharField(
                blank=True,
                choices=[
                    ('panneau', 'Panneau'),
                    ('onduleur', 'Onduleur'),
                    ('batterie', 'Batterie'),
                    ('structure', 'Structure'),
                    ('cable', 'Câble'),
                    ('protection', 'Protection'),
                    ('pompe', 'Pompe'),
                    ('variateur', 'Variateur'),
                    ('compteur', 'Compteur'),
                    ('accessoire', 'Accessoire'),
                    ('service', 'Service'),
                ],
                help_text="Type d'équipement (optionnel) pour filtrer les "
                          "slots de chantier par TYPE, quel que soit le "
                          "libellé de la catégorie. Vide = non typée "
                          "(comportement historique).",
                max_length=20,
                null=True,
            ),
        ),
    ]
