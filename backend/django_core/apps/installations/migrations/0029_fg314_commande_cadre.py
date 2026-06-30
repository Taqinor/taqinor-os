# Generated for FG314 — Commandes-cadres / contrats annuels (blanket orders).
# Additif : on AJOUTE trois tables (CommandeCadre, CommandeCadreLigne,
# AppelCommande). Aucune colonne d'une table existante n'est modifiée. Aucune
# migration destructive.
# Cross-app : STRING-FK vers stock.Fournisseur / stock.Produit.
# Noms d'index ≤ 30 caractères : idx_cc_co_statut, idx_cc_co_fournisseur,
# idx_ccl_cadre, idx_appel_co_ligne.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0028_fg312_approbation_bcf'),
        ('stock', '0023_fg54_fg61_fg62_fg63_fg64_stock_features'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CommandeCadre',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reference', models.CharField(max_length=50)),
                ('intitule', models.CharField(max_length=255)),
                ('date_debut', models.DateField(blank=True, null=True)),
                ('date_fin', models.DateField(blank=True, null=True)),
                ('statut', models.CharField(choices=[('brouillon', 'Brouillon'), ('actif', 'Actif'), ('clos', 'Clos')], default='brouillon', max_length=20)),
                ('note', models.TextField(blank=True, null=True)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('date_modification', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='installations_commandes_cadre', to='authentication.company')),
                ('fournisseur', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='installations_commandes_cadre', to='stock.fournisseur')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installations_commandes_cadre_creees', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Commande-cadre',
                'verbose_name_plural': 'Commandes-cadres',
                'ordering': ['-date_creation'],
                'unique_together': {('company', 'reference')},
            },
        ),
        migrations.CreateModel(
            name='CommandeCadreLigne',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('designation', models.CharField(blank=True, max_length=255, null=True)),
                ('prix_negocie', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('volume_engage', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('commande_cadre', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lignes', to='installations.commandecadre')),
                ('produit', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installations_commande_cadre_lignes', to='stock.produit')),
            ],
            options={
                'verbose_name': 'Ligne de commande-cadre',
                'verbose_name_plural': 'Lignes de commande-cadre',
            },
        ),
        migrations.CreateModel(
            name='AppelCommande',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantite', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('date_appel', models.DateField(blank=True, null=True)),
                ('note', models.TextField(blank=True, null=True)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='installations_appels_commande', to='authentication.company')),
                ('ligne', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='appels', to='installations.commandecadreligne')),
                ('chantier', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installations_appels_commande', to='installations.installation')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installations_appels_commande_crees', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': "Commande d'appel",
                'verbose_name_plural': "Commandes d'appel",
                'ordering': ['-date_creation'],
            },
        ),
        migrations.AddIndex(
            model_name='commandecadre',
            index=models.Index(fields=['company', 'statut'], name='idx_cc_co_statut'),
        ),
        migrations.AddIndex(
            model_name='commandecadre',
            index=models.Index(fields=['company', 'fournisseur'], name='idx_cc_co_fournisseur'),
        ),
        migrations.AddIndex(
            model_name='commandecadreligne',
            index=models.Index(fields=['commande_cadre'], name='idx_ccl_cadre'),
        ),
        migrations.AddIndex(
            model_name='appelcommande',
            index=models.Index(fields=['company', 'ligne'], name='idx_appel_co_ligne'),
        ),
    ]
