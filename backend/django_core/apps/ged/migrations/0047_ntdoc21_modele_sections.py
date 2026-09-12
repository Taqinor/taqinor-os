"""NTDOC21 — sections conditionnelles sur les modèles de documents.

Additive : une colonne JSON optionnelle (liste vide par défaut). Un modèle
existant garde donc EXACTEMENT le comportement GED27 (corps unique, simple
substitution de jetons). Aucune donnée existante n'est modifiée.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ged', '0046_ntdoc14_journal_source_ref'),
    ]

    operations = [
        migrations.AddField(
            model_name='modeledocument',
            name='sections',
            field=models.JSONField(
                blank=True, default=list,
                verbose_name='sections conditionnelles'),
        ),
    ]
