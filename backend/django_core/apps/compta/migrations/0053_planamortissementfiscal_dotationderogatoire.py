"""XACC16 — Amortissements dérogatoires (double plan comptable / fiscal).

Additif : ``PlanAmortissementFiscal`` (plan fiscal parallèle optionnel,
OneToOne vers ``PlanAmortissement``) et ``DotationDerogatoire`` (différence
annuelle comptable-vs-fiscal, postable 65941/1351 ou 1351/7594). Aucun modèle
existant n'est modifié ; l'absence de plan fiscal laisse FG119 intact.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0014_customuser_account_lockout'),
        ('compta', '0052_chargeconstateeavance_dotationetalement'),
    ]

    operations = [
        migrations.CreateModel(
            name='PlanAmortissementFiscal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('mode', models.CharField(choices=[('lineaire', 'Linéaire'), ('degressif', 'Dégressif')], default='degressif', max_length=10, verbose_name='Mode fiscal')),
                ('duree_annees', models.PositiveIntegerField(verbose_name='Durée fiscale (années)')),
                ('coefficient_degressif', models.DecimalField(blank=True, decimal_places=2, max_digits=4, null=True, verbose_name='Coefficient dégressif fiscal')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='plans_amortissement_fiscaux', to='authentication.company', verbose_name='Société')),
                ('plan_comptable', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='plan_fiscal', to='compta.planamortissement', verbose_name='Plan comptable (FG119)')),
            ],
            options={
                'verbose_name': "Plan d'amortissement fiscal",
                'verbose_name_plural': "Plans d'amortissement fiscaux",
                'ordering': ['-date_creation', '-id'],
            },
        ),
        migrations.CreateModel(
            name='DotationDerogatoire',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('annee', models.PositiveIntegerField(verbose_name='Exercice (année)')),
                ('date_dotation', models.DateField(verbose_name='Date de dotation')),
                ('dotation_comptable', models.DecimalField(decimal_places=2, default='0', max_digits=14, verbose_name='Dotation comptable')),
                ('dotation_fiscale', models.DecimalField(decimal_places=2, default='0', max_digits=14, verbose_name='Dotation fiscale')),
                ('difference', models.DecimalField(decimal_places=2, default='0', max_digits=14, verbose_name='Différence (dérogatoire)')),
                ('posted', models.BooleanField(default=False, verbose_name='Postée au grand livre')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='dotations_derogatoires', to='authentication.company', verbose_name='Société')),
                ('plan_fiscal', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='dotations_derogatoires', to='compta.planamortissementfiscal', verbose_name='Plan fiscal')),
                ('ecriture', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='dotations_derogatoires', to='compta.ecriturecomptable', verbose_name='Écriture comptable')),
            ],
            options={
                'verbose_name': 'Dotation dérogatoire',
                'verbose_name_plural': 'Dotations dérogatoires',
                'ordering': ['plan_fiscal_id', 'annee'],
            },
        ),
        migrations.AddConstraint(
            model_name='dotationderogatoire',
            constraint=models.UniqueConstraint(fields=('plan_fiscal', 'annee'), name='uniq_dotation_derogatoire_plan_annee'),
        ),
    ]
