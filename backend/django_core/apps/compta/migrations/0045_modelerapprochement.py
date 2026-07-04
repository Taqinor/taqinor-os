"""XACC4 — Modèles de rapprochement (règles de contrepartie automatique).

Additif : nouveau modèle, aucune donnée existante touchée.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0014_customuser_account_lockout'),
        ('compta', '0044_plancomptable_regime_tva'),
    ]

    operations = [
        migrations.CreateModel(
            name='ModeleRapprochement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('libelle', models.CharField(max_length=120, verbose_name='Libellé')),
                ('type_motif', models.CharField(choices=[('contient', 'Le libellé contient'), ('regex', 'Expression régulière')], default='contient', max_length=10, verbose_name='Type de motif')),
                ('motif', models.CharField(max_length=200, verbose_name='Motif (libellé relevé)')),
                ('taux_tva', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, verbose_name='Taux de TVA (%)')),
                ('montant_fixe', models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True, verbose_name='Montant fixe')),
                ('auto', models.BooleanField(default=False, verbose_name='Application automatique')),
                ('actif', models.BooleanField(default=True, verbose_name='Actif')),
                ('priorite', models.PositiveIntegerField(default=100, verbose_name='Priorité (plus petit = prioritaire)')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='modeles_rapprochement', to='authentication.company', verbose_name='Société')),
                ('compte_contrepartie', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='modeles_rapprochement', to='compta.comptecomptable', verbose_name='Compte de contrepartie')),
            ],
            options={
                'verbose_name': 'Modèle de rapprochement',
                'verbose_name_plural': 'Modèles de rapprochement',
                'ordering': ['priorite', 'libelle'],
            },
        ),
    ]
