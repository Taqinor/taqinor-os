# Generated for FG310 — Demande d'achat (réquisition) → approbation.
# Additif : on AJOUTE deux tables (DemandeAchat, DemandeAchatLigne). Aucune
# colonne d'une table existante n'est modifiée. Aucune migration destructive.
# Cross-app : références STRING-FK vers stock.Fournisseur et stock.Produit
# (dépendance sur la dernière migration stock pour garantir leur existence).
# Noms d'index ≤ 30 caractères : idx_da_co_statut, idx_da_co_chantier.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0025_fg309_retenue_garantie'),
        ('stock', '0023_fg54_fg61_fg62_fg63_fg64_stock_features'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='DemandeAchat',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reference', models.CharField(max_length=50)),
                ('objet', models.CharField(max_length=255)),
                ('priorite', models.CharField(choices=[('basse', 'Basse'), ('normale', 'Normale'), ('haute', 'Haute'), ('urgente', 'Urgente')], default='normale', max_length=10)),
                ('date_besoin', models.DateField(blank=True, null=True)),
                ('statut', models.CharField(choices=[('brouillon', 'Brouillon'), ('soumise', 'Soumise'), ('approuvee', 'Approuvée'), ('refusee', 'Refusée'), ('commandee', 'Commandée')], default='brouillon', max_length=20)),
                ('motif_refus', models.TextField(blank=True, null=True)),
                ('date_decision', models.DateTimeField(blank=True, null=True)),
                ('note', models.TextField(blank=True, null=True)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('date_modification', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='installations_demandes_achat', to='authentication.company')),
                ('chantier', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='demandes_achat', to='installations.installation')),
                ('programme', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='demandes_achat', to='installations.projet')),
                ('fournisseur_suggere', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installations_demandes_achat_suggerees', to='stock.fournisseur')),
                ('approuvee_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installations_demandes_achat_approuvees', to=settings.AUTH_USER_MODEL)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installations_demandes_achat_creees', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': "Demande d'achat",
                'verbose_name_plural': "Demandes d'achat",
                'ordering': ['-date_creation'],
                'unique_together': {('company', 'reference')},
            },
        ),
        migrations.CreateModel(
            name='DemandeAchatLigne',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('designation', models.CharField(blank=True, max_length=255, null=True)),
                ('quantite', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('prix_estime', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('demande', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lignes', to='installations.demandeachat')),
                ('produit', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installations_demande_achat_lignes', to='stock.produit')),
            ],
            options={
                'verbose_name': "Ligne de demande d'achat",
                'verbose_name_plural': "Lignes de demande d'achat",
            },
        ),
        migrations.AddIndex(
            model_name='demandeachat',
            index=models.Index(fields=['company', 'statut'], name='idx_da_co_statut'),
        ),
        migrations.AddIndex(
            model_name='demandeachat',
            index=models.Index(fields=['company', 'chantier'], name='idx_da_co_chantier'),
        ),
    ]
