# NTRET18 — Connecteur e-commerce : ConnexionEcommerce, ProduitSync,
# CommandeSync. [GATED: Shopify API] — structure + no-op sans clé.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('authentication', '0027_ntadm22_customuser_is_taqinor_support'),
    ]

    operations = [
        migrations.CreateModel(
            name='ConnexionEcommerce',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name='ID'),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'plateforme',
                    models.CharField(
                        choices=[
                            ('shopify', 'Shopify'),
                            ('woocommerce', 'WooCommerce')],
                        max_length=20),
                ),
                (
                    'boutique_url',
                    models.URLField(
                        blank=True, default='',
                        help_text=(
                            'URL de la boutique (ex. '
                            'https://ma-boutique.myshopify.com).')),
                ),
                (
                    'actif',
                    models.BooleanField(
                        default=False,
                        help_text=(
                            'Interrupteur applicatif — ne remplace PAS la '
                            'clé API : sans clé en .env, la synchronisation '
                            'reste no-op même si actif=True.')),
                ),
                ('derniere_sync_catalogue', models.DateTimeField(blank=True, null=True)),
                ('derniere_sync_commandes', models.DateTimeField(blank=True, null=True)),
                (
                    'company',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='%(app_label)s_%(class)s_set',
                        to='authentication.company', verbose_name='Société'),
                ),
            ],
            options={
                'verbose_name': 'Connexion e-commerce',
                'verbose_name_plural': 'Connexions e-commerce',
                'ordering': ['plateforme'],
            },
        ),
        migrations.CreateModel(
            name='ProduitSync',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name='ID'),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'produit_id',
                    models.PositiveIntegerField(
                        help_text=(
                            'Référence opaque vers stock.Produit.id '
                            '(jamais une FK).')),
                ),
                ('vendable_en_ligne', models.BooleanField(default=True)),
                (
                    'external_product_id',
                    models.CharField(blank=True, default='', max_length=100),
                ),
                ('derniere_sync', models.DateTimeField(blank=True, null=True)),
                (
                    'dernier_statut',
                    models.CharField(
                        choices=[
                            ('ok', 'Synchronisé'), ('erreur', 'Erreur'),
                            ('en_attente', 'En attente')],
                        default='en_attente', max_length=12),
                ),
                ('dernier_message', models.TextField(blank=True, default='')),
                (
                    'connexion',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='produits',
                        to='ecommerce_connect.connexionecommerce'),
                ),
                (
                    'company',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='%(app_label)s_%(class)s_set',
                        to='authentication.company', verbose_name='Société'),
                ),
            ],
            options={
                'verbose_name': 'Produit synchronisé',
                'verbose_name_plural': 'Produits synchronisés',
                'ordering': ['-updated_at'],
            },
        ),
        migrations.CreateModel(
            name='CommandeSync',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name='ID'),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('external_order_id', models.CharField(max_length=100)),
                (
                    'facture_id',
                    models.PositiveIntegerField(
                        blank=True, null=True,
                        help_text=(
                            'Référence opaque vers ventes.Facture.id '
                            '(jamais une FK).')),
                ),
                (
                    'statut',
                    models.CharField(
                        choices=[('traitee', 'Traitée'), ('erreur', 'Erreur')],
                        max_length=10),
                ),
                ('message', models.TextField(blank=True, default='')),
                ('payload_brut', models.JSONField(blank=True, default=dict)),
                (
                    'connexion',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='commandes',
                        to='ecommerce_connect.connexionecommerce'),
                ),
                (
                    'company',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='%(app_label)s_%(class)s_set',
                        to='authentication.company', verbose_name='Société'),
                ),
            ],
            options={
                'verbose_name': 'Commande synchronisée',
                'verbose_name_plural': 'Commandes synchronisées',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='connexionecommerce',
            constraint=models.UniqueConstraint(
                fields=('company', 'plateforme'),
                name='uniq_connexionecommerce_company_plateforme'),
        ),
        migrations.AddConstraint(
            model_name='produitsync',
            constraint=models.UniqueConstraint(
                fields=('connexion', 'produit_id'),
                name='uniq_produitsync_connexion_produit'),
        ),
        migrations.AddConstraint(
            model_name='commandesync',
            constraint=models.UniqueConstraint(
                fields=('connexion', 'external_order_id'),
                name='uniq_commandesync_connexion_external_order'),
        ),
    ]
