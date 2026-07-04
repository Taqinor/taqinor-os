import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('qhse', '0042_xqhs13_objectif_qhse'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='RisqueOpportunite',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type_ro', models.CharField(choices=[('risque', 'Risque'), ('opportunite', 'Opportunité')], default='risque', max_length=15, verbose_name='Type')),
                ('processus', models.CharField(blank=True, default='', max_length=255, verbose_name='Processus concerné')),
                ('description', models.TextField(verbose_name='Description')),
                ('probabilite_inherente', models.PositiveSmallIntegerField(default=1, verbose_name='Probabilité inhérente (1–5)')),
                ('gravite_inherente', models.PositiveSmallIntegerField(default=1, verbose_name='Gravité inhérente (1–5)')),
                ('criticite_inherente', models.PositiveSmallIntegerField(default=1, verbose_name='Criticité inhérente')),
                ('probabilite_residuelle', models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='Probabilité résiduelle (1–5)')),
                ('gravite_residuelle', models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='Gravité résiduelle (1–5)')),
                ('criticite_residuelle', models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='Criticité résiduelle')),
                ('actions_traitement', models.TextField(blank=True, default='', verbose_name='Actions de traitement')),
                ('date_revue', models.DateField(blank=True, null=True, verbose_name='Date de revue')),
                ('frequence_revue_jours', models.PositiveIntegerField(default=180, verbose_name='Fréquence de revue (jours)')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='qhse_risques_opportunites', to='authentication.company', verbose_name='Société')),
                ('responsable', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='qhse_risques_opportunites', to=settings.AUTH_USER_MODEL, verbose_name='Responsable')),
            ],
            options={
                'verbose_name': 'Risque / opportunité',
                'verbose_name_plural': 'Risques / opportunités',
                'ordering': ['-id'],
            },
        ),
        migrations.CreateModel(
            name='RisqueOpportuniteCapa',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('capa', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='risques_opportunites_liees', to='qhse.actioncorrectivepreventive', verbose_name='CAPA')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='qhse_risque_capa', to='authentication.company', verbose_name='Société')),
                ('risque_opportunite', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='capa_liees', to='qhse.risqueopportunite', verbose_name='Risque / opportunité')),
            ],
            options={
                'verbose_name': 'CAPA liée à un risque/opportunité',
                'verbose_name_plural': 'CAPA liées à des risques/opportunités',
            },
        ),
        migrations.CreateModel(
            name='PartieInteressee',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('partie', models.CharField(max_length=255, verbose_name='Partie')),
                ('attentes', models.TextField(blank=True, default='', verbose_name='Attentes / exigences')),
                ('pertinence', models.CharField(choices=[('faible', 'Faible'), ('moyenne', 'Moyenne'), ('forte', 'Forte')], default='moyenne', max_length=10, verbose_name='Pertinence SMQ')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='qhse_parties_interessees', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Partie intéressée',
                'verbose_name_plural': 'Parties intéressées',
                'ordering': ['-id'],
            },
        ),
        migrations.CreateModel(
            name='ContexteOrganisation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('swot', models.TextField(blank=True, default='', verbose_name='SWOT')),
                ('perimetre_smq', models.TextField(blank=True, default='', verbose_name='Périmètre du SMQ')),
                ('date_modification', models.DateTimeField(auto_now=True, verbose_name='Modifié le')),
                ('company', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='qhse_contexte_organisation', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': "Contexte de l'organisation",
                'verbose_name_plural': "Contextes de l'organisation",
            },
        ),
        migrations.AddConstraint(
            model_name='risqueopportunitecapa',
            constraint=models.UniqueConstraint(fields=['risque_opportunite', 'capa'], name='qhse_risque_capa_uniq'),
        ),
    ]
