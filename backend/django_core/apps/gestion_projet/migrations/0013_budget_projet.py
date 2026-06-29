# Generated for PROJ21 -- Budget projet (lignes par catégorie).

import django.db.models.deletion
from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0012_customuser_must_change_password_and_more'),
        ('gestion_projet', '0012_indisponibilite'),
    ]

    operations = [
        migrations.CreateModel(
            name='BudgetProjet',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('libelle', models.CharField(blank=True, default='', max_length=200, verbose_name='Libellé')),
                ('version', models.PositiveIntegerField(default=1, verbose_name='Version')),
                ('statut', models.CharField(choices=[('brouillon', 'Brouillon'), ('valide', 'Validé'), ('archive', 'Archivé')], default='brouillon', max_length=10, verbose_name='Statut')),
                ('devise', models.CharField(default='MAD', max_length=3, verbose_name='Devise')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gestion_projet_budgets', to='authentication.company', verbose_name='Société')),
                ('projet', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='budgets', to='gestion_projet.projet', verbose_name='Projet')),
            ],
            options={
                'verbose_name': 'Budget projet',
                'verbose_name_plural': 'Budgets projet',
                'ordering': ['projet', '-version', '-id'],
                'indexes': [models.Index(fields=['projet', 'version'], name='gp_budget_proj_ver_idx')],
            },
        ),
        migrations.CreateModel(
            name='LigneBudgetProjet',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('categorie', models.CharField(choices=[('materiel', 'Matériel'), ('main_oeuvre', "Main-d'œuvre"), ('sous_traitance', 'Sous-traitance'), ('divers', 'Divers')], default='materiel', max_length=14, verbose_name='Catégorie')),
                ('libelle', models.CharField(max_length=200, verbose_name='Libellé')),
                ('quantite', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name='Quantité')),
                ('pu', models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True, verbose_name='Prix unitaire')),
                ('montant_prevu', models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=14, verbose_name='Montant prévu')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('budget', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lignes', to='gestion_projet.budgetprojet', verbose_name='Budget')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gestion_projet_lignes_budget', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Ligne de budget projet',
                'verbose_name_plural': 'Lignes de budget projet',
                'ordering': ['budget', 'categorie', 'id'],
                'indexes': [models.Index(fields=['budget', 'categorie'], name='gp_ligne_bud_cat_idx')],
            },
        ),
    ]
