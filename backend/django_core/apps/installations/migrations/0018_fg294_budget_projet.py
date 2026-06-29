# Generated for FG294 — Budget projet vs réel (engagé/dépensé).
# Additif : on AJOUTE deux tables (BudgetProjet, BudgetEngagement). Aucune
# colonne d'une table existante n'est modifiée. Aucune migration destructive.
#
# BudgetEngagement référence stock.BonCommandeFournisseur /
# stock.FactureFournisseur par string-FK (rattacher un coût d'achat à un budget
# de programme — aucune FK native n'existe). Les modèles stock ne sont jamais
# importés côté Python ; la dépendance de migration sur `stock` suffit.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0012_customuser_must_change_password_and_more'),
        ('installations', '0017_fg292_projet_tache'),
        ('stock', '0023_fg54_fg61_fg62_fg63_fg64_stock_features'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='BudgetProjet',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('devise', models.CharField(default='MAD', max_length=8)),
                ('budget_materiel', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('budget_main_oeuvre', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('budget_sous_traitance', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('budget_divers', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('tarif_jour_mo', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('seuil_alerte_pct', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('note', models.TextField(blank=True, null=True)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('date_modification', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='installations_budgets_projet', to='authentication.company')),
                ('projet', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='budget', to='installations.projet')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installations_budgets_projet_crees', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Budget de projet',
                'verbose_name_plural': 'Budgets de projet',
                'ordering': ['-date_creation'],
            },
        ),
        migrations.CreateModel(
            name='BudgetEngagement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source', models.CharField(choices=[('bon_commande', 'Bon de commande fournisseur'), ('facture', 'Facture fournisseur')], default='bon_commande', max_length=12)),
                ('categorie', models.CharField(choices=[('materiel', 'Matériel'), ('main_oeuvre', "Main-d'œuvre"), ('sous_traitance', 'Sous-traitance'), ('divers', 'Divers')], default='materiel', max_length=14)),
                ('libelle', models.CharField(blank=True, max_length=200, null=True)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='installations_budget_engagements', to='authentication.company')),
                ('budget', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='engagements', to='installations.budgetprojet')),
                ('bon_commande', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='installations_budget_engagements', to='stock.boncommandefournisseur')),
                ('facture', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='installations_budget_engagements', to='stock.facturefournisseur')),
            ],
            options={
                'verbose_name': 'Engagement de budget',
                'verbose_name_plural': 'Engagements de budget',
                'ordering': ['budget_id', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='budgetprojet',
            index=models.Index(fields=['company', 'projet'], name='idx_budgproj_co_proj'),
        ),
        migrations.AddIndex(
            model_name='budgetengagement',
            index=models.Index(fields=['company', 'budget'], name='idx_budgeng_co_budg'),
        ),
    ]
