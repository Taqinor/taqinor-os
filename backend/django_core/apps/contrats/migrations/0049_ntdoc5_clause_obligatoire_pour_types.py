"""NTDOC5 — Bibliothèque de clauses OBLIGATOIRES par type de contrat.

Purement ADDITIF : un seul champ nullable-par-défaut (liste JSON vide) sur
``Clause``. Toutes les clauses existantes gardent une liste vide = clause
facultative, donc comportement inchangé. Aucune clause n'est renommée.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contrats', '0048_ntdoc3_commentaire_redline'),
    ]

    operations = [
        migrations.AddField(
            model_name='clause',
            name='obligatoire_pour_types',
            field=models.JSONField(blank=True, default=list, verbose_name='Obligatoire pour les types de contrat'),
        ),
    ]
