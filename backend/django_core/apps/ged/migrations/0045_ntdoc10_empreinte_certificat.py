"""NTDOC10 — empreinte SHA-256 du certificat de complétion.

Additive : une colonne texte optionnelle (vide par défaut) indexée, utilisée
par l'endpoint public de vérification d'intégrité. Aucune donnée existante
n'est modifiée.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ged', '0044_ntdoc9_acces_tentative_ko'),
    ]

    operations = [
        migrations.AddField(
            model_name='demandesignaturedocument',
            name='empreinte_certificat',
            field=models.CharField(
                blank=True, db_index=True, default='', max_length=64,
                verbose_name='empreinte du certificat (SHA-256)'),
        ),
    ]
