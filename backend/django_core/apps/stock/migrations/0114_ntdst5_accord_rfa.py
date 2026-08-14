# NTDST5 — accords de remise arrière (RFA) fournisseur.
# Additive : une nouvelle table.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0028_company_tours_actifs'),
        ('stock', '0113_ntdst_consignation_parametres'),
    ]

    operations = [
        migrations.CreateModel(
            name='AccordRFAFournisseur',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('periode_debut', models.DateField()),
                ('periode_fin', models.DateField()),
                ('seuil_ca_achat', models.DecimalField(decimal_places=2, default=0, help_text="CA d'achat (HT) à atteindre pour déclencher la remise. 0 = remise due dès le premier dirham.", max_digits=14)),
                ('taux_pct', models.DecimalField(blank=True, decimal_places=2, help_text='Remise en % du CA réalisé (exclusif avec montant_fixe).', max_digits=5, null=True)),
                ('montant_fixe', models.DecimalField(blank=True, decimal_places=2, help_text='Remise forfaitaire (exclusif avec taux_pct).', max_digits=14, null=True)),
                ('statut', models.CharField(choices=[('actif', 'Actif'), ('clos', 'Clos')], default='actif', max_length=20)),
                ('note', models.TextField(blank=True, default='')),
                ('avoir_genere', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='accord_rfa_source', to='stock.avoirfournisseur')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('fournisseur', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='accords_rfa', to='stock.fournisseur')),
            ],
            options={
                'verbose_name': 'Accord RFA fournisseur',
                'verbose_name_plural': 'Accords RFA fournisseur',
                'ordering': ['-periode_debut', '-id'],
                'indexes': [models.Index(fields=['company', 'statut'], name='idx_accordrfa_co_statut')],
            },
        ),
        migrations.AddConstraint(
            model_name='accordrfafournisseur',
            constraint=models.CheckConstraint(check=models.Q(('periode_fin__gte', models.F('periode_debut'))), name='stock_accordrfa_periode_coherente'),
        ),
        migrations.AddConstraint(
            model_name='accordrfafournisseur',
            constraint=models.UniqueConstraint(fields=('company', 'fournisseur', 'periode_debut', 'periode_fin'), name='stock_accordrfa_co_fourn_periode_uniq'),
        ),
    ]
