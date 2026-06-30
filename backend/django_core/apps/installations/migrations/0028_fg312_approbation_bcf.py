# Generated for FG312 — Paliers d'approbation de BCF par seuil.
# Additif : on AJOUTE deux tables (SeuilApprobationBCF, ApprobationBCF). Aucune
# colonne d'une table existante n'est modifiée. Aucune migration destructive.
# Cross-app : ApprobationBCF.bcf en STRING-FK vers stock.BonCommandeFournisseur.
# Noms d'index ≤ 30 caractères : idx_seuilbcf_co_actif, idx_appbcf_co_bcf.

from decimal import Decimal
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0027_fg311_rfq'),
        ('stock', '0023_fg54_fg61_fg62_fg63_fg64_stock_features'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SeuilApprobationBCF',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('seuil_responsable', models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=12)),
                ('actif', models.BooleanField(default=True)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('date_modification', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='installations_seuils_approbation_bcf', to='authentication.company')),
            ],
            options={
                'verbose_name': "Seuil d'approbation BCF",
                'verbose_name_plural': "Seuils d'approbation BCF",
                'ordering': ['-date_creation'],
            },
        ),
        migrations.CreateModel(
            name='ApprobationBCF',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('palier', models.CharField(choices=[('responsable', 'Responsable'), ('admin', 'Administrateur')], max_length=20)),
                ('montant_approuve', models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=12)),
                ('note', models.TextField(blank=True, null=True)),
                ('date_approbation', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='installations_approbations_bcf', to='authentication.company')),
                ('bcf', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='installations_approbations', to='stock.boncommandefournisseur')),
                ('approuve_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installations_approbations_bcf', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Approbation BCF',
                'verbose_name_plural': 'Approbations BCF',
                'ordering': ['-date_approbation'],
                'unique_together': {('company', 'bcf')},
            },
        ),
        migrations.AddIndex(
            model_name='seuilapprobationbcf',
            index=models.Index(fields=['company', 'actif'], name='idx_seuilbcf_co_actif'),
        ),
        migrations.AddIndex(
            model_name='approbationbcf',
            index=models.Index(fields=['company', 'bcf'], name='idx_appbcf_co_bcf'),
        ),
    ]
