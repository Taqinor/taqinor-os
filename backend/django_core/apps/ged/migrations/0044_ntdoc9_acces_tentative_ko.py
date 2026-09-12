"""NTDOC9 — nouveau type d'accès « tentative publique échouée ».

Additive et non destructive : seule la liste `choices` de
`JournalAcces.type_acces` s'élargit (aucune donnée existante n'est touchée,
`max_length=14` inchangé — `tentative_ko` fait 12 caractères).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ged', '0043_zged15_backfill_document_reference'),
    ]

    operations = [
        migrations.AlterField(
            model_name='journalacces',
            name='type_acces',
            field=models.CharField(
                choices=[
                    ('apercu', 'Aperçu'),
                    ('telechargement', 'Téléchargement'),
                    ('public', 'Accès public (lien)'),
                    ('consultation', 'Consultation'),
                    ('tentative_ko', 'Tentative publique échouée'),
                ],
                default='consultation', max_length=14,
                verbose_name="type d'accès"),
        ),
    ]
