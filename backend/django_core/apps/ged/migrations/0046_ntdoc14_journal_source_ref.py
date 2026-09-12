"""NTDOC14 — référence opaque de la source d'un accès journalisé.

Additive : une colonne texte optionnelle (vide par défaut) indexée, qui permet
d'attribuer un accès public à la salle de données et au VIEWER dont il vient.
Aucune donnée existante n'est modifiée.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ged', '0045_ntdoc10_empreinte_certificat'),
    ]

    operations = [
        migrations.AddField(
            model_name='journalacces',
            name='source_ref',
            field=models.CharField(
                blank=True, db_index=True, default='', max_length=64,
                verbose_name="référence de la source d'accès"),
        ),
    ]
