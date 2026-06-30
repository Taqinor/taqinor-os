# Generated for FG315 — Suivi import / dédouanement.
# Additif : on AJOUTE une seule table (DossierImport). Aucune colonne d'une
# table existante n'est modifiée. Aucune migration destructive.
# Cross-app : STRING-FK vers stock.Fournisseur / stock.BonCommandeFournisseur.
# Noms d'index ≤ 30 caractères : idx_imp_co_statut, idx_imp_co_fournisseur.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0029_fg314_commande_cadre'),
        ('stock', '0023_fg54_fg61_fg62_fg63_fg64_stock_features'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='DossierImport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reference', models.CharField(max_length=50)),
                ('designation', models.CharField(max_length=255)),
                ('incoterm', models.CharField(blank=True, choices=[('exw', "EXW — À l'usine"), ('fob', 'FOB — Franco à bord'), ('cfr', 'CFR — Coût et fret'), ('cif', 'CIF — Coût, assurance, fret'), ('dap', 'DAP — Rendu au lieu'), ('ddp', 'DDP — Rendu droits acquittés')], max_length=3, null=True)),
                ('numero_bl', models.CharField(blank=True, max_length=80, null=True)),
                ('numero_conteneur', models.CharField(blank=True, max_length=40, null=True)),
                ('port_arrivee', models.CharField(blank=True, max_length=120, null=True)),
                ('date_depart', models.DateField(blank=True, null=True)),
                ('date_arrivee_port', models.DateField(blank=True, null=True)),
                ('date_dedouanement', models.DateField(blank=True, null=True)),
                ('statut_douane', models.CharField(choices=[('commande', 'Commandé'), ('expedie', 'Expédié'), ('arrive_port', 'Arrivé au port'), ('en_douane', 'En cours de dédouanement'), ('dedouane', 'Dédouané'), ('livre', 'Livré')], default='commande', max_length=20)),
                ('note', models.TextField(blank=True, null=True)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('date_modification', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='installations_dossiers_import', to='authentication.company')),
                ('fournisseur', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installations_dossiers_import', to='stock.fournisseur')),
                ('bon_commande', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installations_dossiers_import', to='stock.boncommandefournisseur')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installations_dossiers_import_crees', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': "Dossier d'import",
                'verbose_name_plural': "Dossiers d'import",
                'ordering': ['-date_creation'],
                'unique_together': {('company', 'reference')},
            },
        ),
        migrations.AddIndex(
            model_name='dossierimport',
            index=models.Index(fields=['company', 'statut_douane'], name='idx_imp_co_statut'),
        ),
        migrations.AddIndex(
            model_name='dossierimport',
            index=models.Index(fields=['company', 'fournisseur'], name='idx_imp_co_fournisseur'),
        ),
    ]
