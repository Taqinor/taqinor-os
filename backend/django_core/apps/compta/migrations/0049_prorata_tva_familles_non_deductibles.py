"""XACC11 — Prorata de déduction TVA & TVA non déductible.

Additif : ``coefficient_prorata_tva`` sur ``ExerciceComptable`` (défaut 100 %
= comportement actuel intact) + nouveau modèle ``FamilleTvaNonDeductible``.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0014_customuser_account_lockout'),
        ('compta', '0048_obligationfiscale'),
    ]

    operations = [
        migrations.AddField(
            model_name='exercicecomptable',
            name='coefficient_prorata_tva',
            field=models.DecimalField(
                decimal_places=2, default=100, max_digits=5,
                verbose_name='Coefficient de prorata TVA (%)'),
        ),
        migrations.CreateModel(
            name='FamilleTvaNonDeductible',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('famille', models.CharField(max_length=60, verbose_name='Famille (clef DC22)')),
                ('libelle', models.CharField(blank=True, default='', max_length=150, verbose_name='Libellé')),
                ('actif', models.BooleanField(default=True, verbose_name='Actif')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='familles_tva_non_deductibles', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Famille TVA non déductible',
                'verbose_name_plural': 'Familles TVA non déductibles',
                'ordering': ['famille'],
                'unique_together': {('company', 'famille')},
            },
        ),
    ]
