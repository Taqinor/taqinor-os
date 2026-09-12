"""NTDATA37 — un abonnement peut viser un Dashboard ou une SavedQuery.

Deux opérations ADDITIVES et inertes :

  * ``target_kind`` gagne deux choix (``dashboard``/``query``). Les choix sont
    une contrainte APPLICATIVE en Django — la colonne reste le même varchar(20)
    et aucune ligne existante n'est touchée ;
  * ``cible_id`` est un entier NULLABLE, NULL pour tous les rapports existants
    (les 3 rapports figés n'ont pas de cible). Ajouter une colonne nullable
    sans défaut est une opération de métadonnées en PostgreSQL.

Aucun abonnement existant ne change de comportement.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reporting', '0020_ntcon34_kpi_btp'),
    ]

    operations = [
        migrations.AlterField(
            model_name='savedreport',
            name='target_kind',
            field=models.CharField(
                choices=[('sales', 'Ventes'), ('stock', 'Stock'),
                         ('service', 'Service'),
                         ('dashboard', 'Tableau de bord'),
                         ('query', 'Requête sauvegardée')],
                default='sales', max_length=20),
        ),
        migrations.AddField(
            model_name='savedreport',
            name='cible_id',
            field=models.PositiveIntegerField(
                blank=True, null=True, verbose_name='Cible',
                help_text='Identifiant du tableau de bord ou de la requête '
                          'sauvegardée visée. Vide pour les rapports '
                          'Ventes / Stock / Service.'),
        ),
    ]
