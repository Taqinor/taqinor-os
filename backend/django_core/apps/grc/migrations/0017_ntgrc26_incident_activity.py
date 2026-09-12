# NTGRC26 — chronologie (« chatter ») d'un incident de sécurité.
# Table NEUVE, purement additive. `timestamp` a pour défaut `timezone.now`
# (callable) : l'horodatage est SERVEUR, jamais fourni par le client.

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0030_aud704_identite_employeur'),
        ('grc', '0016_ntgrc25_incident_securite'),
    ]

    operations = [
        migrations.CreateModel(
            name='IncidentActivity',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('type', models.CharField(
                    choices=[('log', 'Événement automatique'),
                             ('note', 'Note manuelle')],
                    default='note', max_length=6, verbose_name='Type')),
                ('detail', models.TextField(
                    blank=True, default='', verbose_name='Détail')),
                ('auteur', models.CharField(
                    blank=True, default='',
                    help_text="Instantané du nom d'utilisateur, posé côté "
                              'serveur.',
                    max_length=150, verbose_name='Auteur')),
                ('timestamp', models.DateTimeField(
                    default=django.utils.timezone.now,
                    help_text="Horodatage SERVEUR de l'événement.",
                    verbose_name='Horodatage')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
                ('incident', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='activites', to='grc.incidentsecurite',
                    verbose_name='Incident')),
            ],
            options={
                'verbose_name': "Ligne de chronologie d'incident",
                'verbose_name_plural': "Chronologie d'incident",
                'ordering': ['-timestamp', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='incidentactivity',
            index=models.Index(fields=['company', 'incident'],
                               name='grc_incidentact_co_inc_idx'),
        ),
    ]
