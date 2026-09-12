# NTOBS1 — page de statut publique (composants + incidents). Migration écrite
# à la main (INTERDIT manage.py sur cette lane) ; state Django équivalent à ce
# que `makemigrations` produirait pour `apps/statuspage/models.py`.
import django.db.models.deletion
from django.db import migrations, models
from django.utils import timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('authentication', '0032_customuser_calendrier_hegirien'),
    ]

    operations = [
        migrations.CreateModel(
            name='ComponentStatus',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('nom', models.CharField(max_length=120, verbose_name='Composant')),
                ('region', models.CharField(blank=True, default='', help_text='Ex. « EU-West/Hetzner ». Libre, jamais un identifiant interne.', max_length=60, verbose_name='Région')),
                ('statut', models.CharField(choices=[('operational', 'Opérationnel'), ('degraded', 'Dégradé'), ('partial_outage', 'Panne partielle'), ('major_outage', 'Panne majeure')], default='operational', max_length=20, verbose_name='Statut')),
                ('derniere_verification', models.DateTimeField(blank=True, null=True, verbose_name='Dernière vérification')),
                ('company', models.ForeignKey(blank=True, help_text='NULL = composant système, partagé entre tous les tenants.', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='statuspage_composants', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Composant (statut public)',
                'verbose_name_plural': 'Composants (statut public)',
                'ordering': ['nom', 'region'],
            },
        ),
        migrations.CreateModel(
            name='IncidentPublic',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('titre', models.CharField(max_length=255, verbose_name='Titre')),
                ('severite', models.CharField(choices=[('mineure', 'Mineure'), ('majeure', 'Majeure'), ('critique', 'Critique')], default='mineure', max_length=10, verbose_name='Sévérité')),
                ('statut', models.CharField(choices=[('investigating', 'En investigation'), ('identified', 'Cause identifiée'), ('monitoring', 'Sous surveillance'), ('resolved', 'Résolu')], default='investigating', max_length=20, verbose_name='Statut')),
                ('region', models.CharField(blank=True, default='', max_length=60, verbose_name='Région')),
                ('debute_le', models.DateTimeField(default=timezone.now, verbose_name='Débuté le')),
                ('resolu_le', models.DateTimeField(blank=True, null=True, verbose_name='Résolu le')),
                ('postmortem_markdown', models.TextField(blank=True, default='', verbose_name='Post-mortem')),
                ('postmortem_publie_le', models.DateTimeField(blank=True, null=True, verbose_name='Post-mortem publié le')),
                ('company', models.ForeignKey(blank=True, help_text='NULL = incident système, visible de tous les tenants.', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='statuspage_incidents', to='authentication.company', verbose_name='Société')),
                ('composants', models.ManyToManyField(blank=True, related_name='incidents', to='statuspage.componentstatus', verbose_name='Composants touchés')),
            ],
            options={
                'verbose_name': 'Incident (public)',
                'verbose_name_plural': 'Incidents (publics)',
                'ordering': ['-debute_le'],
            },
        ),
        migrations.CreateModel(
            name='IncidentUpdate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('statut', models.CharField(choices=[('investigating', 'En investigation'), ('identified', 'Cause identifiée'), ('monitoring', 'Sous surveillance'), ('resolved', 'Résolu')], max_length=20, verbose_name='Statut au moment de la mise à jour')),
                ('message', models.TextField(verbose_name='Message')),
                ('horodatage', models.DateTimeField(default=timezone.now, verbose_name='Horodatage')),
                ('incident', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='updates', to='statuspage.incidentpublic', verbose_name='Incident')),
            ],
            options={
                'verbose_name': "Mise à jour d'incident",
                'verbose_name_plural': "Mises à jour d'incident",
                'ordering': ['horodatage'],
            },
        ),
        migrations.AddIndex(
            model_name='componentstatus',
            index=models.Index(fields=['nom', 'region'], name='statuspage_component_nom_idx'),
        ),
        migrations.AddIndex(
            model_name='incidentpublic',
            index=models.Index(fields=['statut', '-debute_le'], name='statuspage_incident_statut_idx'),
        ),
        migrations.AddIndex(
            model_name='incidentpublic',
            index=models.Index(fields=['region'], name='statuspage_incident_region_idx'),
        ),
    ]
