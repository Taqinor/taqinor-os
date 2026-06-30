# Generated for FG306 — Factures & règlements des sous-traitants chantier (AP).
# Additif : on AJOUTE deux tables (FactureSousTraitant, PaiementSousTraitant).
# Aucune colonne d'une table existante n'est modifiée. Aucune migration
# destructive. Montants INTERNES — jamais client-facing.
# Noms d'index ≤ 30 caractères : idx_fst_co_statut, idx_fst_co_soustrait,
# idx_pst_co_facture.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0021_fg305_ordre_sous_traitance'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='FactureSousTraitant',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('numero', models.CharField(blank=True, max_length=80, null=True)),
                ('montant_ht', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('montant_tva', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('montant_ttc', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('date_facture', models.DateField(blank=True, null=True)),
                ('date_echeance', models.DateField(blank=True, null=True)),
                ('statut', models.CharField(choices=[('brouillon', 'Brouillon'), ('a_payer', 'À payer'), ('partielle', 'Partiellement payée'), ('payee', 'Payée'), ('annulee', 'Annulée')], default='brouillon', max_length=20)),
                ('note', models.TextField(blank=True, null=True)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('date_modification', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='installations_factures_sous_traitant', to='authentication.company')),
                ('sous_traitant', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='installations_factures', to='installations.soustraitant')),
                ('ordre', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='factures', to='installations.ordresoustraitance')),
                ('chantier', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installations_factures_sous_traitant', to='installations.installation')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installations_factures_sous_traitant_creees', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Facture sous-traitant',
                'verbose_name_plural': 'Factures sous-traitant',
                'ordering': ['-date_creation'],
            },
        ),
        migrations.CreateModel(
            name='PaiementSousTraitant',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('montant', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('date_paiement', models.DateField(blank=True, null=True)),
                ('mode', models.CharField(choices=[('virement', 'Virement'), ('cheque', 'Chèque'), ('especes', 'Espèces'), ('effet', 'Effet / traite'), ('autre', 'Autre')], default='virement', max_length=20)),
                ('reference_paiement', models.CharField(blank=True, max_length=120, null=True)),
                ('note', models.TextField(blank=True, null=True)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='installations_paiements_sous_traitant', to='authentication.company')),
                ('facture', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='paiements', to='installations.facturesoustraitant')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installations_paiements_sous_traitant_crees', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Paiement sous-traitant',
                'verbose_name_plural': 'Paiements sous-traitant',
                'ordering': ['-date_paiement', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='facturesoustraitant',
            index=models.Index(fields=['company', 'statut'], name='idx_fst_co_statut'),
        ),
        migrations.AddIndex(
            model_name='facturesoustraitant',
            index=models.Index(fields=['company', 'sous_traitant'], name='idx_fst_co_soustrait'),
        ),
        migrations.AddIndex(
            model_name='paiementsoustraitant',
            index=models.Index(fields=['company', 'facture'], name='idx_pst_co_facture'),
        ),
    ]
