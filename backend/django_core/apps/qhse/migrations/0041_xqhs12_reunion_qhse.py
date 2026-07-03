import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('qhse', '0040_xqhs11_clause_norme'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ReunionQhse',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type_reunion', models.CharField(choices=[('revue_direction', 'Revue de direction'), ('comite_hygiene_securite', "Comité d'hygiène et de sécurité"), ('reunion_hse', 'Réunion HSE')], default='reunion_hse', max_length=25, verbose_name='Type')),
                ('date_reunion', models.DateField(blank=True, null=True, verbose_name='Date')),
                ('participants', models.JSONField(blank=True, default=list, verbose_name='Participants')),
                ('ordre_du_jour', models.TextField(blank=True, default='', verbose_name='Ordre du jour')),
                ('pv', models.TextField(blank=True, default='', verbose_name='PV / minutes')),
                ('attachment_ids', models.JSONField(blank=True, default=list, verbose_name='IDs pièces jointes')),
                ('checklist_revue_direction', models.JSONField(blank=True, default=dict, verbose_name='Checklist ISO 9.3')),
                ('rapport_annuel', models.TextField(blank=True, default='', verbose_name='Rapport annuel (CSH)')),
                ('statut', models.CharField(choices=[('planifiee', 'Planifiée'), ('tenue', 'Tenue'), ('cloturee', 'Clôturée')], default='planifiee', max_length=10, verbose_name='Statut')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='qhse_reunions', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Réunion QHSE',
                'verbose_name_plural': 'Réunions QHSE',
                'ordering': ['-date_reunion', '-id'],
            },
        ),
        migrations.CreateModel(
            name='DecisionReunion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('texte', models.TextField(verbose_name='Décision')),
                ('capa_id', models.PositiveIntegerField(blank=True, null=True, verbose_name='ID de la CAPA créée')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='qhse_decisions_reunion', to='authentication.company', verbose_name='Société')),
                ('responsable', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='qhse_decisions_reunion', to=settings.AUTH_USER_MODEL, verbose_name='Responsable')),
                ('reunion', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='decisions', to='qhse.reunionqhse', verbose_name='Réunion')),
            ],
            options={
                'verbose_name': 'Décision de réunion',
                'verbose_name_plural': 'Décisions de réunion',
                'ordering': ['-id'],
            },
        ),
        migrations.AddIndex(
            model_name='reunionqhse',
            index=models.Index(fields=['company', 'type_reunion'], name='qhse_reunion_co_type'),
        ),
    ]
