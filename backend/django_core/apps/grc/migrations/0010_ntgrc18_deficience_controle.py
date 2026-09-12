# NTGRC18 — constat de déficience + liens risque / CAPA QHSE. Table NEUVE.
# Les liens vers le registre des risques et vers un CAPA QHSE sont des
# identifiants TEXTE (`*_ref`) : `grc` n'importe JAMAIS `apps.qhse.models`.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0030_aud704_identite_employeur'),
        ('grc', '0009_ntgrc17_test_controle'),
    ]

    operations = [
        migrations.CreateModel(
            name='DeficienceControle',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('gravite', models.CharField(
                    choices=[('mineure', 'Mineure'),
                             ('significative', 'Significative'),
                             ('majeure', 'Majeure')],
                    default='mineure', max_length=14,
                    verbose_name='Gravité')),
                ('description', models.TextField(
                    blank=True, default='', verbose_name='Description')),
                ('remediation', models.TextField(
                    blank=True, default='', verbose_name='Remédiation')),
                ('responsable', models.CharField(
                    blank=True, default='', max_length=160,
                    verbose_name='Responsable')),
                ('echeance', models.DateField(
                    blank=True, null=True, verbose_name='Échéance')),
                ('statut', models.CharField(
                    choices=[('ouverte', 'Ouverte'),
                             ('en_cours', 'En cours de remédiation'),
                             ('corrigee', 'Corrigée')],
                    default='ouverte', max_length=10,
                    verbose_name='Statut')),
                ('risque_entreprise_ref', models.CharField(
                    blank=True, default='',
                    help_text='Identifiant de la `grc.RisqueEntreprise` '
                              'liée.',
                    max_length=64,
                    verbose_name="Risque d'entreprise lié")),
                ('qhse_capa_ref', models.CharField(
                    blank=True, default='',
                    help_text='Identifiant de la '
                              '`qhse.ActionCorrectivePreventive` — référence '
                              'TEXTE, jamais une FK vers une autre app.',
                    max_length=64, verbose_name='CAPA QHSE lié')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
                ('test_controle', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='deficiences', to='grc.testcontrole',
                    verbose_name='Test de contrôle')),
            ],
            options={
                'verbose_name': 'Déficience de contrôle',
                'verbose_name_plural': 'Déficiences de contrôle',
                'ordering': ['-created_at', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='deficiencecontrole',
            index=models.Index(fields=['company', 'statut'],
                               name='grc_deficience_co_statut_idx'),
        ),
        migrations.AddIndex(
            model_name='deficiencecontrole',
            index=models.Index(fields=['company', 'gravite'],
                               name='grc_deficience_co_grav_idx'),
        ),
    ]
