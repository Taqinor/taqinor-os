"""NTDOC4 — Statut ``en_negociation`` du cycle de vie contractuel.

Purement déclaratif et ADDITIF : seule la liste de ``choices`` du champ
``Contrat.statut`` s'élargit (aucune donnée touchée, aucun statut existant
renommé ni supprimé — les contrats en base gardent exactement leur statut).
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contrats', '0049_ntdoc5_clause_obligatoire_pour_types'),
    ]

    operations = [
        migrations.AlterField(
            model_name='contrat',
            name='statut',
            field=models.CharField(choices=[('brouillon', 'Brouillon'), ('en_negociation', 'En négociation'), ('en_approbation', 'En approbation'), ('signe', 'Signé'), ('actif', 'Actif'), ('suspendu', 'Suspendu'), ('resilie', 'Résilié'), ('expire', 'Expiré')], default='brouillon', max_length=20, verbose_name='Statut'),
        ),
    ]
