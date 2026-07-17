import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('authentication', '0024_ntprt1_customuser_portee'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AdminOpsSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('sandbox_duree_defaut_jours', models.PositiveSmallIntegerField(default=14)),
                ('sandbox_grace_purge_jours', models.PositiveSmallIntegerField(default=7)),
                ('seuil_alerte_sieges_pct', models.PositiveSmallIntegerField(default=90)),
                ('retention_evenements_usage_jours', models.PositiveSmallIntegerField(default=180)),
                ('sandbox_autorise', models.BooleanField(default=True)),
                ('date_modification', models.DateTimeField(auto_now=True)),
                ('company', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='adminops_settings', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Réglages Administration (société)',
                'verbose_name_plural': 'Réglages Administration (société)',
            },
        ),
        migrations.CreateModel(
            name='ConfigPackage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('nom', models.CharField(max_length=150)),
                ('version', models.PositiveIntegerField(default=1)),
                ('contenu', models.JSONField(blank=True, default=dict)),
                ('contenu_purge', models.BooleanField(default=False)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('cree_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='config_packages_crees', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Package de configuration',
                'verbose_name_plural': 'Packages de configuration',
                'ordering': ['-date_creation'],
            },
        ),
        migrations.CreateModel(
            name='ConfigPackageApplication',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('package_nom', models.CharField(max_length=150)),
                ('package_version', models.PositiveIntegerField(default=1)),
                ('action', models.CharField(choices=[('previsualisation', 'Prévisualisation'), ('application', 'Application')], max_length=20)),
                ('diff', models.JSONField(blank=True, default=dict)),
                ('date_action', models.DateTimeField(auto_now_add=True)),
                ('applique_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='config_package_applications', to=settings.AUTH_USER_MODEL)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': "Journal d'import de package",
                'verbose_name_plural': "Journaux d'import de package",
                'ordering': ['-date_action'],
            },
        ),
        migrations.CreateModel(
            name='HealthScoreSnapshot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('score', models.PositiveSmallIntegerField()),
                ('sous_scores', models.JSONField(blank=True, default=dict)),
                ('calcule_le', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Instantané health score',
                'verbose_name_plural': 'Instantanés health score',
                'ordering': ['-calcule_le'],
            },
        ),
        migrations.CreateModel(
            name='SandboxEnvironment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('statut', models.CharField(choices=[('en_creation', 'En création'), ('pret', 'Prêt'), ('expire', 'Expiré'), ('echec', 'Échec')], default='en_creation', max_length=20)),
                ('date_expiration', models.DateTimeField()),
                ('prolongations_count', models.PositiveSmallIntegerField(default=0)),
                ('rappel_j3_envoye', models.BooleanField(default=False)),
                ('rappel_48h_envoye', models.BooleanField(default=False)),
                ('erreur', models.TextField(blank=True, default='')),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('cree_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sandbox_environments_crees', to=settings.AUTH_USER_MODEL)),
                ('sandbox_company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sandbox_environments_cibles', to='authentication.company')),
            ],
            options={
                'verbose_name': 'Environnement sandbox',
                'verbose_name_plural': 'Environnements sandbox',
                'ordering': ['-date_creation'],
            },
        ),
        migrations.CreateModel(
            name='EvenementUsage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('module', models.CharField(max_length=60)),
                ('ecran', models.CharField(blank=True, default='', max_length=120)),
                ('horodatage', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('utilisateur', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='evenements_usage', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': "Événement d'usage",
                'verbose_name_plural': "Événements d'usage",
                'ordering': ['-horodatage'],
                'indexes': [models.Index(fields=['company', 'module', 'horodatage'], name='adminops_ev_company_3ad737_idx')],
            },
        ),
    ]
