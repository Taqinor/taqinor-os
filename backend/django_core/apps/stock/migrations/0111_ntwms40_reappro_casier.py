# NTWMS40 — seuil de réappro par casier picking + tâche de réappro interne.
# Additive : deux nouvelles tables ; un casier sans seuil n'est jamais dû,
# donc aucune société existante ne change de comportement.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0028_company_tours_actifs'),
        ('installations', '0100_photochecklistmeta_tenantmodel_timestamps'),
        ('stock', '0110_ntwms39_historique_casier'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SeuilReapproCasier',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('seuil', models.PositiveIntegerField(default=0, help_text='Sous cette quantité, le casier est dû en réappro interne.')),
                ('quantite_cible', models.PositiveIntegerField(blank=True, help_text='Quantité à remonter (vide = seuil × 2).', null=True)),
                ('actif', models.BooleanField(default=True)),
                ('bin', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='seuil_reappro_stock', to='installations.binlocation')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('produit', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='seuils_reappro_casier', to='stock.produit')),
            ],
            options={
                'verbose_name': 'Seuil de réappro casier',
                'verbose_name_plural': 'Seuils de réappro casier',
                'ordering': ['bin_id'],
                'indexes': [models.Index(fields=['company', 'actif'], name='idx_seuilreap_co_actif')],
            },
        ),
        migrations.CreateModel(
            name='TacheReapproInterne',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('quantite', models.PositiveIntegerField(default=0)),
                ('statut', models.CharField(choices=[('a_faire', 'À faire'), ('faite', 'Faite'), ('annulee', 'Annulée')], default='a_faire', max_length=20)),
                ('note', models.TextField(blank=True, default='')),
                ('bin_cible', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='taches_reappro_cible_stock', to='installations.binlocation')),
                ('bin_source', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='taches_reappro_source_stock', to='installations.binlocation')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('cree_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='taches_reappro_interne_creees', to=settings.AUTH_USER_MODEL)),
                ('produit', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='taches_reappro_interne', to='stock.produit')),
            ],
            options={
                'verbose_name': 'Tâche de réappro interne',
                'verbose_name_plural': 'Tâches de réappro interne',
                'ordering': ['-created_at'],
                'indexes': [models.Index(fields=['company', 'statut'], name='idx_reappro_co_statut')],
            },
        ),
        migrations.AddConstraint(
            model_name='tachereapprointerne',
            constraint=models.UniqueConstraint(condition=models.Q(('statut', 'a_faire')), fields=('company', 'bin_cible'), name='stock_reappro_bin_cible_ouverte_uniq'),
        ),
    ]
