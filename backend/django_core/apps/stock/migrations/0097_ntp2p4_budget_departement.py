"""NTP2P4 — budget d'engagement par département.

Additif pur : deux tables neuves (``BudgetDepartement`` / ``EngagementBudget``)
et un interrupteur ``AchatsParametres.budget_departement_actif`` à ``False``.
Tant qu'il n'est pas activé, la soumission d'une demande d'achat n'exécute
aucun contrôle budgétaire — comportement historique strictement inchangé.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('achats', '0003_protect_fournisseur_prix'),
        ('authentication', '0027_ntadm22_customuser_is_taqinor_support'),
        ('installations', '0102_ntp2p2_approbation_achat'),
        ('rh', '0083_yhard1_encrypt_dossieremploye'),
        ('stock', '0096_pv5_fiche_technique_specs'),
    ]

    operations = [
        migrations.AddField(
            model_name='achatsparametres',
            name='budget_departement_actif',
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name='BudgetDepartement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('periodicite', models.CharField(choices=[('mensuelle', 'Mensuelle'), ('annuelle', 'Annuelle')], default='annuelle', max_length=10, verbose_name='Périodicité')),
                ('annee', models.PositiveIntegerField(verbose_name='Année')),
                ('mois', models.PositiveSmallIntegerField(default=0, verbose_name='Mois (0 = budget annuel)')),
                ('montant_alloue', models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name='Montant alloué (MAD)')),
                ('actif', models.BooleanField(default=True, verbose_name='Actif')),
                ('note', models.TextField(blank=True, default='')),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('departement', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='budgets_achat', to='rh.departement', verbose_name='Département')),
            ],
            options={
                'verbose_name': 'Budget départemental',
                'verbose_name_plural': 'Budgets départementaux',
                'ordering': ['-annee', '-mois', 'id'],
            },
        ),
        migrations.CreateModel(
            name='EngagementBudget',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('montant', models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name='Montant engagé (MAD)')),
                ('statut', models.CharField(choices=[('actif', 'Actif'), ('libere', 'Libéré'), ('consomme', 'Consommé')], default='actif', max_length=10)),
                ('note', models.TextField(blank=True, default='')),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('bon_commande', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='engagements_budget', to='achats.boncommandefournisseur', verbose_name='Bon de commande')),
                ('budget', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='engagements', to='stock.budgetdepartement', verbose_name='Budget')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('demande_achat', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='engagements_budget', to='installations.demandeachat', verbose_name="Demande d'achat")),
            ],
            options={
                'verbose_name': 'Engagement budgétaire',
                'verbose_name_plural': 'Engagements budgétaires',
                'ordering': ['-date_creation', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='budgetdepartement',
            index=models.Index(fields=['company', 'annee'], name='idx_budgdep_co_annee'),
        ),
        migrations.AddIndex(
            model_name='budgetdepartement',
            index=models.Index(fields=['company', 'departement'], name='idx_budgdep_co_dept'),
        ),
        migrations.AddConstraint(
            model_name='budgetdepartement',
            constraint=models.UniqueConstraint(fields=('company', 'departement', 'periodicite', 'annee', 'mois'), name='uniq_budget_dep_periode'),
        ),
        migrations.AddIndex(
            model_name='engagementbudget',
            index=models.Index(fields=['company', 'statut'], name='idx_engbud_co_statut'),
        ),
        migrations.AddIndex(
            model_name='engagementbudget',
            index=models.Index(fields=['budget', 'statut'], name='idx_engbud_bud_stat'),
        ),
    ]
