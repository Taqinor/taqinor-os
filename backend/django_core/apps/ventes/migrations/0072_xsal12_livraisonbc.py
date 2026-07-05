# XSAL12 — Livraisons partielles et reliquats sur le bon de commande client.
# Additive/reversible: two brand-new tables, no changes to existing ones.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0001_initial'),
        ('ventes', '0071_xsal6_plancommission'),
    ]

    operations = [
        migrations.CreateModel(
            name='LivraisonBC',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_livraison', models.DateField()),
                ('note', models.CharField(blank=True, default='', max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('bon_commande', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='livraisons', to='ventes.boncommande')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='livraisons_bc', to='authentication.company')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='livraisons_bc_creees', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Livraison (BC)',
                'verbose_name_plural': 'Livraisons (BC)',
                'ordering': ['-date_livraison', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='LigneLivraisonBC',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantite_livree', models.DecimalField(decimal_places=2, max_digits=10)),
                ('ligne_devis', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lignes_livraison_bc', to='ventes.lignedevis')),
                ('livraison', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lignes', to='ventes.livraisonbc')),
            ],
            options={
                'verbose_name': 'Ligne de livraison (BC)',
                'verbose_name_plural': 'Lignes de livraison (BC)',
            },
        ),
    ]
