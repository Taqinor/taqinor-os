# NTDST14 — van sales : stock embarqué véhicule.
# Additive : une nouvelle table.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0028_company_tours_actifs'),
        ('flotte', '0058_garage_contratvehicule_fournisseur_id_ref'),
        ('stock', '0114_ntdst5_accord_rfa'),
    ]

    operations = [
        migrations.CreateModel(
            name='StockVehicule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('quantite_embarquee', models.PositiveIntegerField(default=0)),
                ('actif_flotte', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='stocks_embarques', to='flotte.actifflotte')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('produit', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='stocks_vehicule', to='stock.produit')),
            ],
            options={
                'verbose_name': 'Stock embarqué véhicule',
                'verbose_name_plural': 'Stocks embarqués véhicule',
                'ordering': ['actif_flotte_id', 'produit_id'],
                'indexes': [models.Index(fields=['company', 'actif_flotte'], name='idx_stockveh_co_actif')],
            },
        ),
        migrations.AddConstraint(
            model_name='stockvehicule',
            constraint=models.UniqueConstraint(fields=('company', 'actif_flotte', 'produit'), name='stock_stockvehicule_co_actif_produit_uniq'),
        ),
    ]
