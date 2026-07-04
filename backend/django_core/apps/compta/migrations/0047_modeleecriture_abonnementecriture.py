"""XACC8 — Modèles d'écriture, écritures récurrentes & extourne automatique.

Additif : trois nouveaux modèles, aucune donnée existante touchée.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0014_customuser_account_lockout'),
        ('compta', '0046_plancomptable_inventaire_permanent'),
    ]

    operations = [
        migrations.CreateModel(
            name='ModeleEcriture',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('libelle', models.CharField(max_length=150, verbose_name='Libellé')),
                ('extourne_auto', models.BooleanField(default=False, verbose_name='Extourne automatique')),
                ('actif', models.BooleanField(default=True, verbose_name='Actif')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='modeles_ecriture', to='authentication.company', verbose_name='Société')),
                ('journal', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='modeles_ecriture', to='compta.journal', verbose_name='Journal')),
            ],
            options={
                'verbose_name': "Modèle d'écriture",
                'verbose_name_plural': "Modèles d'écriture",
                'ordering': ['libelle'],
            },
        ),
        migrations.CreateModel(
            name='LigneModeleEcriture',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('libelle', models.CharField(blank=True, default='', max_length=255, verbose_name='Libellé')),
                ('sens', models.CharField(choices=[('debit', 'Débit'), ('credit', 'Crédit')], max_length=6, verbose_name='Sens')),
                ('montant_defaut', models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True, verbose_name='Montant par défaut')),
                ('ordre', models.PositiveIntegerField(default=0, verbose_name='Ordre')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lignes_modele_ecriture', to='authentication.company', verbose_name='Société')),
                ('compte', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='lignes_modele_ecriture', to='compta.comptecomptable', verbose_name='Compte')),
                ('modele', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lignes', to='compta.modeleecriture', verbose_name='Modèle')),
            ],
            options={
                'verbose_name': "Ligne de modèle d'écriture",
                'verbose_name_plural': "Lignes de modèle d'écriture",
                'ordering': ['modele', 'ordre', 'id'],
            },
        ),
        migrations.CreateModel(
            name='AbonnementEcriture',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('libelle', models.CharField(blank=True, default='', max_length=150, verbose_name='Libellé')),
                ('frequence', models.CharField(choices=[('mensuelle', 'Mensuelle'), ('trimestrielle', 'Trimestrielle')], default='mensuelle', max_length=15, verbose_name='Fréquence')),
                ('prochaine_echeance', models.DateField(verbose_name='Prochaine échéance')),
                ('date_fin', models.DateField(blank=True, null=True, verbose_name='Date de fin')),
                ('actif', models.BooleanField(default=True, verbose_name='Actif')),
                ('derniere_generation', models.DateField(blank=True, null=True, verbose_name='Dernière génération')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='abonnements_ecriture', to='authentication.company', verbose_name='Société')),
                ('modele', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='abonnements', to='compta.modeleecriture', verbose_name='Modèle')),
            ],
            options={
                'verbose_name': "Abonnement d'écriture",
                'verbose_name_plural': "Abonnements d'écriture",
                'ordering': ['prochaine_echeance'],
            },
        ),
    ]
