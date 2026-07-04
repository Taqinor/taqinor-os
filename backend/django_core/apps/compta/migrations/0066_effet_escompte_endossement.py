"""XACC34 — Remise à l'escompte & endossement des effets.

Additif : nouveaux statuts ``escompte``/``endosse`` sur ``Effet`` + champs de
traçabilité (agios/intérêts, écritures d'escompte/apurement, bénéficiaire de
l'endossement). Le compte 5520 « crédits d'escompte » est semé à la volée
(``_assurer_compte``, pas de backfill nécessaire ici).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('compta', '0065_immobilisation_capitalisation_facture_fournisseur'),
    ]

    operations = [
        migrations.AlterField(
            model_name='effet',
            name='statut',
            field=models.CharField(choices=[('portefeuille', 'En portefeuille'), ('remis', "Remis à l'encaissement"), ('encaisse', 'Encaissé'), ('paye', 'Payé'), ('impaye', 'Impayé / rejeté'), ('escompte', "Remis à l'escompte"), ('endosse', 'Endossé à un tiers')], default='portefeuille', max_length=15, verbose_name='Statut'),
        ),
        migrations.AddField(
            model_name='effet',
            name='agios_escompte',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True, verbose_name="Agios de l'escompte"),
        ),
        migrations.AddField(
            model_name='effet',
            name='interets_escompte',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True, verbose_name="Intérêts de l'escompte"),
        ),
        migrations.AddField(
            model_name='effet',
            name='date_escompte',
            field=models.DateField(blank=True, null=True, verbose_name="Date de l'escompte"),
        ),
        migrations.AddField(
            model_name='effet',
            name='ecriture_escompte_id',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name="ID de l'écriture d'escompte"),
        ),
        migrations.AddField(
            model_name='effet',
            name='ecriture_apurement_escompte_id',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name="ID de l'écriture d'apurement de l'escompte"),
        ),
        migrations.AddField(
            model_name='effet',
            name='beneficiaire_endossement',
            field=models.CharField(blank=True, default='', max_length=160, verbose_name="Bénéficiaire de l'endossement"),
        ),
        migrations.AddField(
            model_name='effet',
            name='date_endossement',
            field=models.DateField(blank=True, null=True, verbose_name="Date de l'endossement"),
        ),
    ]
