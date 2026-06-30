# Generated for FG316 — Frais d'import & coût de revient débarqué (landed cost).
# Additif : on AJOUTE deux tables (FraisImport, LandedCostLigne). Aucune colonne
# d'une table existante n'est modifiée. Aucune migration destructive.
# Cross-app : LandedCostLigne.produit en STRING-FK vers stock.Produit.
# Noms d'index ≤ 30 caractères : idx_frais_co_dossier, idx_landed_co_dossier.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0030_fg315_dossier_import'),
        ('stock', '0023_fg54_fg61_fg62_fg63_fg64_stock_features'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='FraisImport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('categorie', models.CharField(choices=[('fret', 'Fret maritime / aérien'), ('douane', 'Droits de douane'), ('tva_import', "TVA à l'import"), ('transit', 'Transit / transport interne'), ('manutention', 'Manutention / magasinage'), ('assurance', 'Assurance'), ('autre', 'Autre frais')], default='autre', max_length=20)),
                ('libelle', models.CharField(blank=True, max_length=200, null=True)),
                ('montant', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('date_frais', models.DateField(blank=True, null=True)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='installations_frais_import', to='authentication.company')),
                ('dossier', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='frais', to='installations.dossierimport')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installations_frais_import_crees', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': "Frais d'import",
                'verbose_name_plural': "Frais d'import",
                'ordering': ['dossier_id', 'categorie', 'id'],
            },
        ),
        migrations.CreateModel(
            name='LandedCostLigne',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('designation', models.CharField(blank=True, max_length=255, null=True)),
                ('quantite', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('valeur_fob', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='installations_landed_cost_lignes', to='authentication.company')),
                ('dossier', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='landed_lignes', to='installations.dossierimport')),
                ('produit', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installations_landed_cost_lignes', to='stock.produit')),
            ],
            options={
                'verbose_name': 'Ligne de coût débarqué',
                'verbose_name_plural': 'Lignes de coût débarqué',
                'ordering': ['dossier_id', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='fraisimport',
            index=models.Index(fields=['company', 'dossier'], name='idx_frais_co_dossier'),
        ),
        migrations.AddIndex(
            model_name='landedcostligne',
            index=models.Index(fields=['company', 'dossier'], name='idx_landed_co_dossier'),
        ),
    ]
