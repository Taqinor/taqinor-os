# XSAL1 — Listes de prix clients (détail / revendeur / export).
# Additive/reversible: two brand-new tables, no changes to existing ones.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        ('stock', '0001_initial'),
        ('ventes', '0068_alter_mandatpaiement_expiration_mois_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='ListePrix',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom', models.CharField(max_length=150)),
                ('devise', models.CharField(default='MAD', max_length=10)),
                ('date_debut', models.DateField(blank=True, null=True)),
                ('date_fin', models.DateField(blank=True, null=True)),
                ('archived', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='listes_prix', to='authentication.company')),
            ],
            options={
                'verbose_name': 'Liste de prix',
                'verbose_name_plural': 'Listes de prix',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='LignePrixListe',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('prix_unitaire', models.DecimalField(decimal_places=2, max_digits=10)),
                ('liste', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lignes', to='ventes.listeprix')),
                ('produit', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lignes_liste_prix', to='stock.produit')),
            ],
            options={
                'verbose_name': 'Ligne de liste de prix',
                'verbose_name_plural': 'Lignes de liste de prix',
            },
        ),
        migrations.AlterUniqueTogether(
            name='ligneprixliste',
            unique_together={('liste', 'produit')},
        ),
    ]
