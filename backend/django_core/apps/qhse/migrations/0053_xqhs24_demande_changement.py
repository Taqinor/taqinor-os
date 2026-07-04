import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('qhse', '0052_xqhs23_ncr_ticket_sav'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='DemandeChangement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type_changement', models.CharField(choices=[('procede', 'Procédé'), ('equipement', 'Équipement'), ('organisation', 'Organisation'), ('document', 'Document')], default='procede', max_length=15, verbose_name='Type de changement')),
                ('description', models.TextField(verbose_name='Description')),
                ('justification', models.TextField(blank=True, default='', verbose_name='Justification')),
                ('classification_impact', models.CharField(choices=[('faible', 'Faible'), ('moyen', 'Moyen'), ('fort', 'Fort')], default='faible', max_length=10, verbose_name="Classification d'impact")),
                ('revue_risques', models.TextField(blank=True, default='', verbose_name='Revue des risques')),
                ('documents_formations_impactes', models.TextField(blank=True, default='', verbose_name='Documents/formations impactés')),
                ('date_approbation', models.DateTimeField(blank=True, null=True, verbose_name="Date d'approbation")),
                ('checklist_verification', models.TextField(blank=True, default='', verbose_name='Checklist de vérification avant déploiement')),
                ('statut', models.CharField(choices=[('brouillon', 'Brouillon'), ('en_revue', 'En revue'), ('approuve', 'Approuvé'), ('deploye', 'Déployé'), ('clos', 'Clos'), ('annule', 'Annulé')], default='brouillon', max_length=15, verbose_name='Statut')),
                ('est_temporaire', models.BooleanField(default=False, verbose_name='Changement temporaire')),
                ('date_expiration', models.DateField(blank=True, null=True, verbose_name='Date de réversion prévue')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='qhse_demandes_changement', to='authentication.company', verbose_name='Société')),
                ('evaluation_risque', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='demandes_changement', to='qhse.evaluationrisque', verbose_name='Évaluation des risques liée')),
                ('approbateur', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='qhse_demandes_changement_approuvees', to=settings.AUTH_USER_MODEL, verbose_name='Approbateur')),
            ],
            options={
                'verbose_name': 'Demande de changement (MOC)',
                'verbose_name_plural': 'Demandes de changement (MOC)',
                'ordering': ['-id'],
            },
        ),
        migrations.AddIndex(
            model_name='demandechangement',
            index=models.Index(fields=['company', 'statut'], name='qhse_demchang_co_statut'),
        ),
        migrations.CreateModel(
            name='DemandeChangementCapa',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='qhse_demande_changement_capa', to='authentication.company', verbose_name='Société')),
                ('demande_changement', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='capa_liees', to='qhse.demandechangement', verbose_name='Demande de changement')),
                ('capa', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='demandes_changement_liees', to='qhse.actioncorrectivepreventive', verbose_name='CAPA')),
            ],
            options={
                'verbose_name': 'CAPA liée à une demande de changement',
                'verbose_name_plural': 'CAPA liées à une demande de changement',
                'ordering': ['-id'],
            },
        ),
        migrations.AddConstraint(
            model_name='demandechangementcapa',
            constraint=models.UniqueConstraint(fields=('demande_changement', 'capa'), name='qhse_demchangcapa_dem_capa_uniq'),
        ),
    ]
