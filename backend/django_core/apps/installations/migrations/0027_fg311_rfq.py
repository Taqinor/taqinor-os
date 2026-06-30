# Generated for FG311 — RFQ multi-fournisseurs & comparatif d'offres.
# Additif : on AJOUTE deux tables (RFQ, RFQOffre). Aucune colonne d'une table
# existante n'est modifiée. Aucune migration destructive.
# Cross-app : RFQOffre.fournisseur en STRING-FK vers stock.Fournisseur.
# Noms d'index ≤ 30 caractères : idx_rfq_co_statut, idx_rfqo_co_rfq.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0026_fg310_demande_achat'),
        ('stock', '0023_fg54_fg61_fg62_fg63_fg64_stock_features'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='RFQ',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reference', models.CharField(max_length=50)),
                ('objet', models.CharField(max_length=255)),
                ('date_limite_reponse', models.DateField(blank=True, null=True)),
                ('statut', models.CharField(choices=[('brouillon', 'Brouillon'), ('envoyee', 'Envoyée'), ('cloturee', 'Clôturée')], default='brouillon', max_length=20)),
                ('note', models.TextField(blank=True, null=True)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('date_modification', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='installations_rfqs', to='authentication.company')),
                ('demande', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='rfqs', to='installations.demandeachat')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installations_rfqs_creees', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Demande de prix (RFQ)',
                'verbose_name_plural': 'Demandes de prix (RFQ)',
                'ordering': ['-date_creation'],
                'unique_together': {('company', 'reference')},
            },
        ),
        migrations.CreateModel(
            name='RFQOffre',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fournisseur_nom_libre', models.CharField(blank=True, max_length=255, null=True)),
                ('montant_ht', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('delai_jours', models.PositiveIntegerField(blank=True, null=True)),
                ('validite_jours', models.PositiveIntegerField(blank=True, null=True)),
                ('retenue', models.BooleanField(default=False)),
                ('note', models.TextField(blank=True, null=True)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('date_modification', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='installations_rfq_offres', to='authentication.company')),
                ('rfq', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='offres', to='installations.rfq')),
                ('fournisseur', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installations_rfq_offres', to='stock.fournisseur')),
            ],
            options={
                'verbose_name': 'Offre RFQ',
                'verbose_name_plural': 'Offres RFQ',
                'ordering': ['montant_ht', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='rfq',
            index=models.Index(fields=['company', 'statut'], name='idx_rfq_co_statut'),
        ),
        migrations.AddIndex(
            model_name='rfqoffre',
            index=models.Index(fields=['company', 'rfq'], name='idx_rfqo_co_rfq'),
        ),
    ]
