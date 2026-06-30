# Generated for FG317 — Réceptionné-non-facturé (GR/IR).
# Additif : on AJOUTE une seule table (ReceptionNonFacturee). Aucune colonne
# d'une table existante n'est modifiée. Aucune migration destructive.
# Cross-app : STRING-FK vers stock.ReceptionFournisseur /
# stock.BonCommandeFournisseur / stock.FactureFournisseur.
# Noms d'index ≤ 30 caractères : idx_grir_co_lettre, idx_grir_co_bcf.

from decimal import Decimal
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0031_fg316_landed_cost'),
        ('stock', '0023_fg54_fg61_fg62_fg63_fg64_stock_features'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ReceptionNonFacturee',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('libelle', models.CharField(blank=True, max_length=200, null=True)),
                ('montant_provision', models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=12)),
                ('date_reception', models.DateField(blank=True, null=True)),
                ('lettre', models.BooleanField(default=False)),
                ('date_lettrage', models.DateField(blank=True, null=True)),
                ('note', models.TextField(blank=True, null=True)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('date_modification', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='installations_receptions_non_facturees', to='authentication.company')),
                ('reception', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installations_gr_ir', to='stock.receptionfournisseur')),
                ('bon_commande', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installations_gr_ir', to='stock.boncommandefournisseur')),
                ('facture', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installations_gr_ir', to='stock.facturefournisseur')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installations_gr_ir_crees', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Réceptionné-non-facturé (GR/IR)',
                'verbose_name_plural': 'Réceptionnés-non-facturés (GR/IR)',
                'ordering': ['-date_creation'],
            },
        ),
        migrations.AddIndex(
            model_name='receptionnonfacturee',
            index=models.Index(fields=['company', 'lettre'], name='idx_grir_co_lettre'),
        ),
        migrations.AddIndex(
            model_name='receptionnonfacturee',
            index=models.Index(fields=['company', 'bon_commande'], name='idx_grir_co_bcf'),
        ),
    ]
