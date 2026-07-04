"""XACC24 — Validation RIB marocain + approbation des changements de RIB.

Additif : ``DemandeApprobationRib`` (workflow 4-yeux pour un changement de
RIB fournisseur ; tant que non approuvée, l'ancien RIB reste actif côté
payment run). Le validateur RIB lui-même (``core.rib``, mod 97) est une
fonction pure sans modèle — aucune migration associée.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0014_customuser_account_lockout'),
        ('compta', '0059_budget_revisions_scenarios'),
    ]

    operations = [
        migrations.CreateModel(
            name='DemandeApprobationRib',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fournisseur_id', models.PositiveIntegerField(verbose_name='Fournisseur (id stock)')),
                ('fournisseur_nom', models.CharField(blank=True, default='', max_length=200, verbose_name='Fournisseur')),
                ('ancien_rib', models.CharField(blank=True, default='', max_length=40, verbose_name='Ancien RIB')),
                ('nouveau_rib', models.CharField(max_length=40, verbose_name='Nouveau RIB')),
                ('statut', models.CharField(choices=[('en_attente', 'En attente'), ('approuvee', 'Approuvée'), ('refusee', 'Refusée')], default='en_attente', max_length=12, verbose_name='Statut')),
                ('commentaire_decision', models.TextField(blank=True, default='', verbose_name='Commentaire de décision')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créée le')),
                ('date_decision', models.DateTimeField(blank=True, null=True, verbose_name='Décidée le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='demandes_approbation_rib', to='authentication.company', verbose_name='Société')),
                ('demandeur', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='demandes_rib_demandees', to=settings.AUTH_USER_MODEL, verbose_name='Demandeur')),
                ('decideur', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='demandes_rib_decidees', to=settings.AUTH_USER_MODEL, verbose_name='Décideur')),
            ],
            options={
                'verbose_name': "Demande d'approbation de RIB",
                'verbose_name_plural': "Demandes d'approbation de RIB",
                'ordering': ['-date_creation', '-id'],
            },
        ),
    ]
