"""XACC28 — Refacturation des frais au client (billable expenses).

Additif : ``refacturable``/``taux_marge``/``client_refacturation_id``/
``chantier_refacturation``/``facture_refacturation_id`` sur ``NoteFrais``
(client et facture référencés par id, string-ref — jamais d'import cross-app).
"""
from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('compta', '0062_plafondnotefrais_notefrais_hors_politique'),
    ]

    operations = [
        migrations.AddField(
            model_name='notefrais',
            name='refacturable',
            field=models.BooleanField(default=False, verbose_name='Refacturable au client'),
        ),
        migrations.AddField(
            model_name='notefrais',
            name='taux_marge',
            field=models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=5, verbose_name='Taux de marge à la refacturation (%)'),
        ),
        migrations.AddField(
            model_name='notefrais',
            name='client_refacturation_id',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='Client à refacturer (id crm, string-ref)'),
        ),
        migrations.AddField(
            model_name='notefrais',
            name='chantier_refacturation',
            field=models.CharField(blank=True, default='', max_length=255, verbose_name='Chantier (référence libre)'),
        ),
        migrations.AddField(
            model_name='notefrais',
            name='facture_refacturation_id',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='Facture de refacturation (id ventes, string-ref)'),
        ),
    ]
