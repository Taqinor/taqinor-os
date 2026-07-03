import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('qhse', '0038_xqhs9_certification'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ProgrammeAudit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('annee', models.PositiveIntegerField(verbose_name='Année')),
                ('statut', models.CharField(choices=[('brouillon', 'Brouillon'), ('actif', 'Actif'), ('clos', 'Clôturé')], default='brouillon', max_length=10, verbose_name='Statut')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='qhse_programmes_audit', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': "Programme d'audit",
                'verbose_name_plural': "Programmes d'audit",
                'ordering': ['-annee'],
            },
        ),
        migrations.CreateModel(
            name='AuditPlanifie',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('processus_domaine', models.CharField(max_length=255, verbose_name='Processus / domaine audité')),
                ('date_cible', models.DateField(blank=True, null=True, verbose_name='Date cible')),
                ('statut', models.CharField(choices=[('planifie', 'Planifié'), ('realise', 'Réalisé'), ('en_retard', 'En retard')], default='planifie', max_length=10, verbose_name='Statut')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('audit', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='audit_planifie', to='qhse.audit', verbose_name='Audit instancié')),
                ('auditeur', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='qhse_audits_planifies_conduits', to=settings.AUTH_USER_MODEL, verbose_name='Auditeur assigné')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='qhse_audits_planifies', to='authentication.company', verbose_name='Société')),
                ('grille', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='qhse_audits_planifies', to='qhse.grilleaudit', verbose_name="Grille d'audit")),
                ('programme', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='audits_planifies', to='qhse.programmeaudit', verbose_name='Programme')),
                ('responsable_domaine', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='qhse_audits_planifies_domaines', to=settings.AUTH_USER_MODEL, verbose_name='Responsable du domaine')),
            ],
            options={
                'verbose_name': 'Audit planifié',
                'verbose_name_plural': 'Audits planifiés',
                'ordering': ['date_cible', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='programmeaudit',
            constraint=models.UniqueConstraint(fields=['company', 'annee'], name='qhse_programmeaudit_co_annee_uniq'),
        ),
    ]
