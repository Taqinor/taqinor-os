# Generated for FG318 — Contrats & accords de prix fournisseur.
# Additif : on AJOUTE deux tables (ContratPrixFournisseur, ContratPrixLigne).
# Aucune colonne d'une table existante n'est modifiée. Aucune migration
# destructive.
# Cross-app : STRING-FK vers stock.Fournisseur / stock.Produit.
# Noms d'index ≤ 30 caractères : idx_cpf_co_fournisseur, idx_cpf_co_statut,
# idx_cpl_contrat, idx_cpl_produit.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0032_fg317_gr_ir'),
        ('stock', '0023_fg54_fg61_fg62_fg63_fg64_stock_features'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ContratPrixFournisseur',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reference', models.CharField(max_length=50)),
                ('intitule', models.CharField(max_length=255)),
                ('version', models.PositiveIntegerField(default=1)),
                ('date_debut', models.DateField(blank=True, null=True)),
                ('date_fin', models.DateField(blank=True, null=True)),
                ('statut', models.CharField(choices=[('brouillon', 'Brouillon'), ('actif', 'Actif'), ('expire', 'Expiré')], default='brouillon', max_length=20)),
                ('note', models.TextField(blank=True, null=True)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('date_modification', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='installations_contrats_prix', to='authentication.company')),
                ('fournisseur', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='installations_contrats_prix', to='stock.fournisseur')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installations_contrats_prix_crees', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Contrat de prix fournisseur',
                'verbose_name_plural': 'Contrats de prix fournisseur',
                'ordering': ['-date_creation'],
                'unique_together': {('company', 'reference')},
            },
        ),
        migrations.CreateModel(
            name='ContratPrixLigne',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('designation', models.CharField(blank=True, max_length=255, null=True)),
                ('prix_convenu', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('remise_pct', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ('contrat', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lignes', to='installations.contratprixfournisseur')),
                ('produit', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installations_contrat_prix_lignes', to='stock.produit')),
            ],
            options={
                'verbose_name': 'Ligne de contrat de prix',
                'verbose_name_plural': 'Lignes de contrat de prix',
            },
        ),
        migrations.AddIndex(
            model_name='contratprixfournisseur',
            index=models.Index(fields=['company', 'fournisseur'], name='idx_cpf_co_fournisseur'),
        ),
        migrations.AddIndex(
            model_name='contratprixfournisseur',
            index=models.Index(fields=['company', 'statut'], name='idx_cpf_co_statut'),
        ),
        migrations.AddIndex(
            model_name='contratprixligne',
            index=models.Index(fields=['contrat'], name='idx_cpl_contrat'),
        ),
        migrations.AddIndex(
            model_name='contratprixligne',
            index=models.Index(fields=['produit'], name='idx_cpl_produit'),
        ),
    ]
