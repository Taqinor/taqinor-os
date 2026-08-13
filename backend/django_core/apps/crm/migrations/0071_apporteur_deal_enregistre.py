# NTCRM20 — Registre des apporteurs d'affaires (Deal Registration) : deux
# nouveaux modèles additifs (Apporteur, DealEnregistre). Aucune modification
# de modèle existant.
import django.db.models.deletion
from django.db import migrations, models

import apps.crm.models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        ('crm', '0070_salle_vente'),
    ]

    operations = [
        migrations.CreateModel(
            name='Apporteur',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('nom', models.CharField(max_length=200, verbose_name='Nom')),
                ('type_apporteur', models.CharField(choices=[
                    ('partenaire_installateur', 'Partenaire installateur'),
                    ('courtier', 'Courtier'),
                    ('apporteur_independant', 'Apporteur indépendant'),
                    ('autre', 'Autre')], default='autre', max_length=24)),
                ('contact_email', models.EmailField(blank=True, default='', max_length=254)),
                ('contact_telephone', models.CharField(blank=True, default='', max_length=30)),
                ('taux_commission_pct', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=5, null=True,
                    verbose_name='Taux de commission (%)')),
                ('actif', models.BooleanField(default=True)),
                ('rib', models.CharField(blank=True, default='', max_length=34, verbose_name='RIB')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name='apporteurs', to='authentication.company')),
            ],
            options={
                'verbose_name': "Apporteur d'affaires",
                'verbose_name_plural': "Apporteurs d'affaires",
                'ordering': ['nom'],
            },
        ),
        migrations.CreateModel(
            name='DealEnregistre',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('date_enregistrement', models.DateTimeField(auto_now_add=True)),
                ('statut', models.CharField(choices=[
                    ('en_attente', 'En attente'), ('approuve', 'Approuvé'),
                    ('rejete', 'Rejeté'), ('expire', 'Expiré')],
                    default='en_attente', max_length=10)),
                ('expire_le', models.DateTimeField(
                    default=apps.crm.models._default_deal_expiry)),
                ('montant_commission_estime', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=14, null=True)),
                ('montant_commission_du', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=14, null=True,
                    help_text='Posé à `À_PAYER` par NTCRM22 (acceptation du '
                              'devis lié).',
                    verbose_name='Commission due (MAD)')),
                ('apporteur', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='deals', to='crm.apporteur')),
                ('company', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name='deals_enregistres', to='authentication.company')),
                ('lead', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='deal_enregistre', to='crm.lead')),
            ],
            options={
                'verbose_name': 'Deal enregistré',
                'verbose_name_plural': 'Deals enregistrés',
                'ordering': ['-date_enregistrement'],
            },
        ),
    ]
