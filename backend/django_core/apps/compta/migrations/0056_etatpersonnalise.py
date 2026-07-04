"""XACC19 — Générateur d'états financiers personnalisés.

Additif : ``EtatPersonnalise`` + ``LigneEtatPersonnalise`` (formule =
plages/sommes de comptes signées) + ``ColonneEtatPersonnalise`` (période,
comparatif N-1, budget FG149, écart %). Les états figés (GL/balance/CPC/
bilan/ESG) restent inchangés — ceci est un état additionnel.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0014_customuser_account_lockout'),
        ('compta', '0055_ecarts_change_reevaluation_cloture'),
    ]

    operations = [
        migrations.CreateModel(
            name='EtatPersonnalise',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('libelle', models.CharField(max_length=200, verbose_name='Libellé')),
                ('description', models.CharField(blank=True, default='', max_length=255, verbose_name='Description')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='etats_personnalises', to='authentication.company', verbose_name='Société')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='etats_personnalises_crees', to=settings.AUTH_USER_MODEL, verbose_name='Créé par')),
            ],
            options={
                'verbose_name': 'État personnalisé',
                'verbose_name_plural': 'États personnalisés',
                'ordering': ['libelle', '-id'],
            },
        ),
        migrations.CreateModel(
            name='LigneEtatPersonnalise',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ordre', models.PositiveIntegerField(default=0, verbose_name='Ordre')),
                ('libelle', models.CharField(max_length=200, verbose_name='Libellé')),
                ('type_ligne', models.CharField(choices=[('titre', 'Titre de section'), ('total', 'Ligne calculée (formule)')], default='total', max_length=10, verbose_name='Type de ligne')),
                ('formule', models.CharField(blank=True, default='', max_length=500, verbose_name='Formule (plages de comptes signées)')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lignes_etat_personnalise', to='authentication.company', verbose_name='Société')),
                ('etat', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lignes', to='compta.etatpersonnalise', verbose_name='État personnalisé')),
            ],
            options={
                'verbose_name': "Ligne d'état personnalisé",
                'verbose_name_plural': "Lignes d'état personnalisé",
                'ordering': ['etat_id', 'ordre', 'id'],
            },
        ),
        migrations.CreateModel(
            name='ColonneEtatPersonnalise',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ordre', models.PositiveIntegerField(default=0, verbose_name='Ordre')),
                ('libelle', models.CharField(max_length=100, verbose_name='Libellé')),
                ('type_colonne', models.CharField(choices=[('periode', 'Période'), ('comparatif_n1', 'Comparatif N-1'), ('budget', 'Budget'), ('ecart_pct', 'Écart % (vs colonne précédente)')], default='periode', max_length=15, verbose_name='Type de colonne')),
                ('date_debut', models.DateField(blank=True, null=True, verbose_name='Début')),
                ('date_fin', models.DateField(blank=True, null=True, verbose_name='Fin')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='colonnes_etat_personnalise', to='authentication.company', verbose_name='Société')),
                ('etat', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='colonnes', to='compta.etatpersonnalise', verbose_name='État personnalisé')),
                ('budget', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='colonnes_etat_personnalise', to='compta.budget', verbose_name='Budget (FG149)')),
            ],
            options={
                'verbose_name': "Colonne d'état personnalisé",
                'verbose_name_plural': "Colonnes d'état personnalisé",
                'ordering': ['etat_id', 'ordre', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='etatpersonnalise',
            constraint=models.UniqueConstraint(fields=('company', 'libelle'), name='uniq_etat_personnalise_libelle'),
        ),
    ]
