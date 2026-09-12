# NTGRC17 — tests de contrôle planifiés + preuves. Table NEUVE.
# La pièce de preuve est une CLÉ de stockage (MinIO/GED), jamais un fichier ni
# une FK vers un document d'une autre app.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0030_aud704_identite_employeur'),
        ('grc', '0008_ntgrc16_controle_interne'),
    ]

    operations = [
        migrations.CreateModel(
            name='TestControle',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('date_prevue', models.DateField(
                    blank=True, null=True, verbose_name='Date prévue')),
                ('date_realisee', models.DateField(
                    blank=True, null=True,
                    verbose_name='Date de réalisation')),
                ('testeur', models.CharField(
                    blank=True, default='', max_length=160,
                    verbose_name='Testeur')),
                ('resultat', models.CharField(
                    choices=[('efficace', 'Efficace'),
                             ('deficient', 'Déficient'),
                             ('non_teste', 'Non testé')],
                    default='non_teste', max_length=10,
                    verbose_name='Résultat')),
                ('echantillon_taille', models.PositiveIntegerField(
                    default=0, verbose_name="Taille de l'échantillon")),
                ('conclusion', models.TextField(
                    blank=True, default='', verbose_name='Conclusion')),
                ('piece_preuve_key', models.CharField(
                    blank=True, default='',
                    help_text='Clé de stockage (MinIO/GED) — jamais le '
                              'fichier lui-même.',
                    max_length=500,
                    verbose_name='Clé de la pièce de preuve')),
                ('statut', models.CharField(
                    choices=[('planifie', 'Planifié'), ('realise', 'Réalisé'),
                             ('annule', 'Annulé')],
                    default='planifie', max_length=10,
                    verbose_name='Statut')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='grc_testcontrole_set',
                    to='authentication.company', verbose_name='Société')),
                ('controle', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='tests', to='grc.controleinterne',
                    verbose_name='Contrôle')),
                ('risque_ouvert', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='tests_controle_a_lorigine',
                    to='grc.risqueentreprise',
                    verbose_name='Risque ouvert')),
            ],
            options={
                'verbose_name': 'Test de contrôle',
                'verbose_name_plural': 'Tests de contrôle',
                'ordering': ['-date_prevue', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='testcontrole',
            index=models.Index(fields=['company', 'resultat'],
                               name='grc_testctrl_co_resultat_idx'),
        ),
        migrations.AddIndex(
            model_name='testcontrole',
            index=models.Index(fields=['company', 'date_realisee'],
                               name='grc_testctrl_co_date_idx'),
        ),
    ]
