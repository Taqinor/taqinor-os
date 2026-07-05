"""XACC14 — Emprunts & crédits-bails (financements de la société).

Additive : ``Emprunt`` (paramètres du financement contracté par la société) et
``EcheanceEmprunt`` (tableau d'amortissement, une ligne par mois, postable au
grand livre). Aucun modèle existant n'est modifié.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0014_customuser_account_lockout'),
        ('compta', '0050_fix_uniq_ecriture_par_source_abonnement'),
    ]

    operations = [
        migrations.CreateModel(
            name='Emprunt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reference', models.CharField(blank=True, default='', max_length=80, verbose_name='Référence')),
                ('banque', models.CharField(blank=True, default='', max_length=200, verbose_name='Banque / bailleur')),
                ('type_financement', models.CharField(choices=[('emprunt', 'Emprunt bancaire'), ('leasing', 'Crédit-bail / leasing')], default='emprunt', max_length=10, verbose_name='Type')),
                ('capital', models.DecimalField(decimal_places=2, default='0.00', max_digits=14, verbose_name='Capital emprunté (MAD)')),
                ('taux_annuel', models.DecimalField(decimal_places=3, default='0.000', max_digits=6, verbose_name='Taux annuel (%)')),
                ('duree_mois', models.PositiveIntegerField(default=12, verbose_name='Durée (mois)')),
                ('date_debut', models.DateField(verbose_name='Date de départ')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='emprunts', to='authentication.company', verbose_name='Société')),
                ('compte_capital', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='emprunts_capital', to='compta.comptecomptable', verbose_name='Compte de capital restant dû (classe 1)')),
                ('compte_interets', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='emprunts_interets', to='compta.comptecomptable', verbose_name='Compte de charges financières (classe 6)')),
                ('compte_tresorerie', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='emprunts', to='compta.comptetresorerie', verbose_name='Compte de trésorerie (payeur)')),
            ],
            options={
                'verbose_name': 'Emprunt / crédit-bail',
                'verbose_name_plural': 'Emprunts / crédits-bails',
                'ordering': ['-date_debut', '-id'],
            },
        ),
        migrations.CreateModel(
            name='EcheanceEmprunt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('numero', models.PositiveIntegerField(verbose_name='Rang (1..N)')),
                ('date_echeance', models.DateField(verbose_name="Date d'échéance")),
                ('principal', models.DecimalField(decimal_places=2, default='0.00', max_digits=14, verbose_name='Part de principal')),
                ('interets', models.DecimalField(decimal_places=2, default='0.00', max_digits=14, verbose_name="Part d'intérêts")),
                ('mensualite', models.DecimalField(decimal_places=2, default='0.00', max_digits=14, verbose_name='Mensualité')),
                ('capital_restant_du', models.DecimalField(decimal_places=2, default='0.00', max_digits=14, verbose_name='Capital restant dû après échéance')),
                ('posted', models.BooleanField(default=False, verbose_name='Postée au grand livre')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='echeances_emprunt', to='authentication.company', verbose_name='Société')),
                ('emprunt', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='echeances', to='compta.emprunt', verbose_name='Emprunt')),
                ('ecriture', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='echeances_emprunt', to='compta.ecriturecomptable', verbose_name='Écriture comptable')),
            ],
            options={
                'verbose_name': "Échéance d'emprunt",
                'verbose_name_plural': "Échéances d'emprunt",
                'ordering': ['emprunt_id', 'numero'],
            },
        ),
        migrations.AddConstraint(
            model_name='emprunt',
            constraint=models.UniqueConstraint(condition=models.Q(('reference__gt', '')), fields=('company', 'reference'), name='uniq_emprunt_reference'),
        ),
        migrations.AddConstraint(
            model_name='echeanceemprunt',
            constraint=models.UniqueConstraint(fields=('emprunt', 'numero'), name='uniq_echeance_emprunt_numero'),
        ),
    ]
