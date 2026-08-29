"""Contrainte d'unicité (company, nom) sur les produits ACTIFS SANS SKU.

Deuxième moitié de la fermeture de course décrite dans ``0134`` (qui a
dé-doublonné les données AVANT — l'ordre compte : cette migration échouerait
sur une base contenant encore des homonymes).

Périmètre : ``is_archived=False`` ET (``sku`` NULL ou vide) — le raisonnement
complet (archivage qui libère le nom, jumeaux de SKU légitimes) est dans le
docstring de ``0134`` et dans ``stock.models.Produit.Meta``.

``AddConstraint`` NU (pas de ``concurrent_index_migration`` / YOPSB6) :
  * une ``UniqueConstraint`` déclarée dans ``Meta`` DOIT être posée par
    ``AddConstraint`` pour que l'état Django reste aligné sur ``models.py``
    (sinon ``makemigrations`` redemande la contrainte à chaque exécution) ;
  * ``stock_produit`` est une table de CATALOGUE (quelques centaines de lignes
    par société), pas une table à forte croissance : le verrou de construction
    de l'index se compte en millisecondes. Le helper concurrent vise les
    tables de flux (``crm_lead``, ``ventes_devis``…).

RÉVERSIBLE : oui, sans perte (``RemoveConstraint``, généré automatiquement par
``AddConstraint``).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0134_dedoublonnage_produit_nom_sans_sku'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='produit',
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    ('is_archived', False)) & (
                    models.Q(('sku__isnull', True)) | models.Q(('sku', ''))),
                fields=('company', 'nom'),
                name='stock_produit_company_nom_sans_sku_uniq'),
        ),
    ]
