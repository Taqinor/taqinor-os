# NTGRC16 — bibliothèque des contrôles internes (SOX-lite). Table NEUVE.
# Le `code` est unique PAR SOCIÉTÉ : deux sociétés peuvent légitimement porter
# le même « ACC-01 ».

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0030_aud704_identite_employeur'),
        ('grc', '0007_ntgrc15_revue_risque'),
    ]

    operations = [
        migrations.CreateModel(
            name='ControleInterne',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('code', models.CharField(
                    max_length=40, verbose_name='Code')),
                ('intitule', models.CharField(
                    max_length=200, verbose_name='Intitulé')),
                ('objectif', models.TextField(
                    blank=True, default='', verbose_name='Objectif')),
                ('domaine', models.CharField(
                    choices=[('acces', 'Gestion des accès'),
                             ('segregation_taches', 'Séparation des tâches'),
                             ('cloture_compta', 'Clôture comptable'),
                             ('achats', 'Achats'), ('paie', 'Paie'),
                             ('si', "Système d'information"),
                             ('sauvegarde', 'Sauvegarde & continuité')],
                    default='acces', max_length=20,
                    verbose_name='Domaine')),
                ('type', models.CharField(
                    choices=[('preventif', 'Préventif'),
                             ('detectif', 'Détectif')],
                    default='preventif', max_length=10,
                    verbose_name='Type')),
                ('frequence', models.CharField(
                    choices=[('permanent', 'Permanent'),
                             ('quotidien', 'Quotidien'),
                             ('hebdo', 'Hebdomadaire'),
                             ('mensuel', 'Mensuel'),
                             ('trimestriel', 'Trimestriel'),
                             ('annuel', 'Annuel')],
                    default='mensuel', max_length=12,
                    verbose_name='Fréquence')),
                ('proprietaire', models.CharField(
                    blank=True, default='', max_length=160,
                    verbose_name='Propriétaire')),
                ('reference_cadre', models.CharField(
                    choices=[('ISO27001', 'ISO 27001'), ('SOX', 'SOX'),
                             ('CGNC', 'CGNC'),
                             ('interne', 'Référentiel interne')],
                    default='interne', max_length=12,
                    verbose_name='Référentiel')),
                ('actif', models.BooleanField(
                    default=True, verbose_name='Actif')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='grc_controleinterne_set',
                    to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Contrôle interne',
                'verbose_name_plural': 'Bibliothèque de contrôles internes',
                'ordering': ['code', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='controleinterne',
            constraint=models.UniqueConstraint(
                fields=('company', 'code'),
                name='grc_controleinterne_co_code'),
        ),
        migrations.AddIndex(
            model_name='controleinterne',
            index=models.Index(fields=['company', 'domaine'],
                               name='grc_controle_co_domaine_idx'),
        ),
    ]
