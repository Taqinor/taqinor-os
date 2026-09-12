# NTGRC13 — registre des risques d'ENTREPRISE (ERM). Table NEUVE.
# Distinct de `qhse.EvaluationRisque` (DUERP, risques au poste de travail) :
# ici la maille est l'entreprise, et le risque porte DEUX cotations
# (inhérente / résiduelle), toutes deux CALCULÉES par le modèle.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0030_aud704_identite_employeur'),
        ('grc', '0004_ntgrc8_legal_hold'),
    ]

    operations = [
        migrations.CreateModel(
            name='RisqueEntreprise',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('reference', models.CharField(
                    blank=True, default='', max_length=40,
                    verbose_name='Référence')),
                ('titre', models.CharField(
                    max_length=200, verbose_name='Titre')),
                ('categorie', models.CharField(
                    choices=[('strategique', 'Stratégique'),
                             ('operationnel', 'Opérationnel'),
                             ('financier', 'Financier'),
                             ('conformite', 'Conformité'),
                             ('si', "Système d'information"),
                             ('reputation', 'Réputation'),
                             ('hse', 'HSE')],
                    default='operationnel', max_length=15,
                    verbose_name='Catégorie')),
                ('description', models.TextField(
                    blank=True, default='', verbose_name='Description')),
                ('proprietaire', models.CharField(
                    blank=True, default='', max_length=160,
                    verbose_name='Propriétaire')),
                ('probabilite', models.PositiveSmallIntegerField(
                    default=1, verbose_name='Probabilité (1-5)')),
                ('impact', models.PositiveSmallIntegerField(
                    default=1, verbose_name='Impact (1-5)')),
                ('criticite_inherente', models.PositiveSmallIntegerField(
                    default=1,
                    help_text='Calculée : probabilité × impact (jamais '
                              'saisie).',
                    verbose_name='Criticité inhérente')),
                ('reponse', models.CharField(
                    choices=[('accepter', 'Accepter'), ('reduire', 'Réduire'),
                             ('transferer', 'Transférer'),
                             ('eviter', 'Éviter')],
                    default='reduire', max_length=12,
                    verbose_name='Réponse au risque')),
                ('probabilite_residuelle', models.PositiveSmallIntegerField(
                    default=1, verbose_name='Probabilité résiduelle (1-5)')),
                ('impact_residuel', models.PositiveSmallIntegerField(
                    default=1, verbose_name='Impact résiduel (1-5)')),
                ('criticite_residuelle', models.PositiveSmallIntegerField(
                    default=1,
                    help_text='Calculée : probabilité résiduelle × impact '
                              'résiduel.',
                    verbose_name='Criticité résiduelle')),
                ('statut', models.CharField(
                    choices=[('ouvert', 'Ouvert'), ('traite', 'Traité'),
                             ('surveille', 'Sous surveillance'),
                             ('clos', 'Clos')],
                    default='ouvert', max_length=12,
                    verbose_name='Statut')),
                ('date_revue_prevue', models.DateField(
                    blank=True, null=True,
                    verbose_name='Prochaine revue prévue')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='grc_risqueentreprise_set',
                    to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': "Risque d'entreprise",
                'verbose_name_plural': "Registre des risques d'entreprise",
                'ordering': ['-criticite_inherente', '-id'],
            },
        ),
        migrations.AddConstraint(
            model_name='risqueentreprise',
            constraint=models.UniqueConstraint(
                fields=('company', 'reference'),
                name='grc_risqueentreprise_co_ref'),
        ),
        migrations.AddIndex(
            model_name='risqueentreprise',
            index=models.Index(fields=['company', 'statut'],
                               name='grc_risque_co_statut_idx'),
        ),
        migrations.AddIndex(
            model_name='risqueentreprise',
            index=models.Index(fields=['company', 'date_revue_prevue'],
                               name='grc_risque_co_revue_idx'),
        ),
    ]
