# Hand-written migration (QJ29 — multi-property villa grouping).
# Additive & nullable only: two new optional fields on LigneDevis so quote lines
# can partition into per-villa groups (0 = commun, 1..N = villa N) inside ONE
# document. NULL groupe_index / empty groupe_label = the historical mono-system
# path (byte-for-byte unchanged when unused). Fully revertable.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0045_asbuiltpack_attestationconformite_attestationre_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='lignedevis',
            name='groupe_index',
            field=models.PositiveSmallIntegerField(
                null=True, blank=True,
                help_text='Groupe multi-villa : 0 = commun, 1..N = villa N. '
                          'Vide = document mono-système (comportement historique).'),
        ),
        migrations.AddField(
            model_name='lignedevis',
            name='groupe_label',
            field=models.CharField(
                max_length=80, blank=True, default='',
                help_text='Libellé de la villa/du groupe (ex. « Villa A »). '
                          'Vide = pas de groupe.'),
        ),
    ]
