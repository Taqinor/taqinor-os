# NTDST3 + NTDST30 — consignation client (dépôt-vente) et paramètres négoce.
# Additive : trois nouvelles tables. Le singleton `ParametresNegoce` est créé
# À LA DEMANDE (aucune migration de données, aucune société touchée).

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0028_company_tours_actifs'),
        ('crm', '0001_initial'),
        ('stock', '0112_ntscm9_incident_qualite_fournisseur'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ParametresNegoce',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('consignation_activee', models.BooleanField(default=True, help_text='Active la consignation client (NTDST3). Désactivée, ses endpoints renvoient 403 explicite.')),
                ('van_sales_active', models.BooleanField(default=True, help_text='Active les tournées de vente / stock embarqué (NTDST14).')),
                ('seuil_alerte_rfa_pct', models.PositiveIntegerField(default=80, help_text='Progression (%) du seuil de CA déclenchant la première alerte RFA.')),
                ('heures_tournee_defaut', models.PositiveIntegerField(default=7, help_text="Durée par défaut d'une tournée (heures).")),
                ('atp_horizon_jours', models.PositiveIntegerField(default=30, help_text='Fenêtre de recherche des commandes fournisseur confirmées pour la disponibilité ATP (NTDST10).')),
                ('seuil_alerte_marge_pct', models.DecimalField(blank=True, decimal_places=2, help_text='Seuil de marge moyenne drop-ship sous lequel alerter (NTDST48). Vide = aucune alerte.', max_digits=5, null=True)),
                ('cout_rupture_jour_mad', models.DecimalField(blank=True, decimal_places=2, help_text="Coût estimé d'un jour de rupture (MAD) — alimente le TCO fournisseur (NTSCM26). Vide = le retard ne pèse rien.", max_digits=12, null=True)),
                ('company', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='parametres_negoce_stock', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Paramètres négoce',
                'verbose_name_plural': 'Paramètres négoce',
            },
        ),
        migrations.CreateModel(
            name='DepotConsignation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('quantite_deposee', models.PositiveIntegerField(default=0)),
                ('quantite_consommee_declaree', models.PositiveIntegerField(default=0)),
                ('date_depot', models.DateField()),
                ('adresse_site', models.CharField(blank=True, default='', max_length=255)),
                ('statut', models.CharField(choices=[('actif', 'Actif'), ('clos', 'Clos')], default='actif', max_length=20)),
                ('note', models.TextField(blank=True, default='')),
                ('client', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='depots_consignation_stock', to='crm.client')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('cree_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='depots_consignation_crees', to=settings.AUTH_USER_MODEL)),
                ('emplacement_source', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='depots_consignation', to='stock.emplacementstock')),
                ('produit', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='depots_consignation', to='stock.produit')),
            ],
            options={
                'verbose_name': 'Dépôt de consignation',
                'verbose_name_plural': 'Dépôts de consignation',
                'ordering': ['-date_depot', '-id'],
                'indexes': [models.Index(fields=['company', 'statut'], name='idx_depotcons_co_statut'), models.Index(fields=['company', 'client'], name='idx_depotcons_co_client')],
            },
        ),
        migrations.CreateModel(
            name='DeclarationConsommation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('quantite', models.PositiveIntegerField()),
                ('date_declaration', models.DateField()),
                ('statut', models.CharField(choices=[('declaree', 'Déclarée'), ('facturee', 'Facturée')], default='declaree', max_length=20)),
                ('document_reference', models.CharField(blank=True, default='', help_text='Référence du document de vente émis (NTDST4).', max_length=80)),
                ('note', models.TextField(blank=True, default='')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('declaree_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='declarations_consommation_stock', to=settings.AUTH_USER_MODEL)),
                ('depot', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='declarations', to='stock.depotconsignation')),
            ],
            options={
                'verbose_name': 'Déclaration de consommation',
                'verbose_name_plural': 'Déclarations de consommation',
                'ordering': ['-date_declaration', '-id'],
                'indexes': [models.Index(fields=['company', 'statut'], name='idx_declcons_co_statut')],
            },
        ),
    ]
