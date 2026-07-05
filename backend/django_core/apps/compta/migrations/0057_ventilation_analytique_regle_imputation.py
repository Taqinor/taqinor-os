"""XACC20 — Ventilation analytique en % multi-sections & règles d'auto-imputation.

Additif : ``VentilationAnalytique`` + ``LigneVentilation`` (distribution % sur
plusieurs ``CentreCout`` pour une ``LigneEcriture``) et ``RegleImputation`` +
``LigneRegleImputation`` (règle par compte/tiers/produit → distribution auto).
``LigneEcriture.centre_cout`` (FG150, mono-axe) reste inchangé et prioritaire
en l'absence de ventilation.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0014_customuser_account_lockout'),
        ('compta', '0056_etatpersonnalise'),
    ]

    operations = [
        migrations.CreateModel(
            name='VentilationAnalytique',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ventilations_analytiques', to='authentication.company', verbose_name='Société')),
                ('ligne_ecriture', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='ventilation_analytique', to='compta.ligneecriture', verbose_name="Ligne d'écriture")),
            ],
            options={
                'verbose_name': 'Ventilation analytique',
                'verbose_name_plural': 'Ventilations analytiques',
                'ordering': ['-date_creation', '-id'],
            },
        ),
        migrations.CreateModel(
            name='LigneVentilation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('pourcentage', models.DecimalField(decimal_places=2, default='0', max_digits=5, verbose_name='Pourcentage (%)')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lignes_ventilation', to='authentication.company', verbose_name='Société')),
                ('ventilation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='distributions', to='compta.ventilationanalytique', verbose_name='Ventilation')),
                ('centre_cout', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='lignes_ventilation', to='compta.centrecout', verbose_name='Centre de coût')),
            ],
            options={
                'verbose_name': 'Ligne de ventilation',
                'verbose_name_plural': 'Lignes de ventilation',
                'ordering': ['ventilation_id', 'id'],
            },
        ),
        migrations.CreateModel(
            name='RegleImputation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('libelle', models.CharField(max_length=200, verbose_name='Libellé')),
                ('prefixe_compte', models.CharField(max_length=20, verbose_name='Préfixe de compte (ou plage)')),
                ('tiers_id', models.PositiveIntegerField(blank=True, null=True, verbose_name='Tiers (optionnel)')),
                ('produit_id', models.PositiveIntegerField(blank=True, null=True, verbose_name='Produit (optionnel)')),
                ('priorite', models.PositiveIntegerField(default=100, verbose_name='Priorité (plus petit = prioritaire)')),
                ('actif', models.BooleanField(default=True, verbose_name='Active')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='regles_imputation', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': "Règle d'imputation analytique",
                'verbose_name_plural': "Règles d'imputation analytique",
                'ordering': ['priorite', 'id'],
            },
        ),
        migrations.CreateModel(
            name='LigneRegleImputation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('pourcentage', models.DecimalField(decimal_places=2, default='0', max_digits=5, verbose_name='Pourcentage (%)')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lignes_regle_imputation', to='authentication.company', verbose_name='Société')),
                ('regle', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='distributions', to='compta.regleimputation', verbose_name='Règle')),
                ('centre_cout', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='lignes_regle_imputation', to='compta.centrecout', verbose_name='Centre de coût')),
            ],
            options={
                'verbose_name': "Ligne de règle d'imputation",
                'verbose_name_plural': "Lignes de règle d'imputation",
                'ordering': ['regle_id', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='ligneventilation',
            constraint=models.UniqueConstraint(fields=('ventilation', 'centre_cout'), name='uniq_ventilation_centre_cout'),
        ),
        migrations.AddConstraint(
            model_name='ligneregleimputation',
            constraint=models.UniqueConstraint(fields=('regle', 'centre_cout'), name='uniq_regle_imputation_centre_cout'),
        ),
    ]
