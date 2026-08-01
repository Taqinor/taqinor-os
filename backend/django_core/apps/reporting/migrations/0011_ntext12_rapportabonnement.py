"""NTEXT12 — abonnements d'envoi planifié d'un rapport (additif, réversible)."""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        ('reporting', '0010_ntext10_rapportdefinition'),
    ]

    operations = [
        migrations.CreateModel(
            name='RapportAbonnement',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('cron', models.CharField(
                    blank=True, default='',
                    help_text='Expression cron 5 champs (ex. « 0 8 * * 1 » = '
                              'lundi 8 h). Vide = jamais planifié.',
                    max_length=120, verbose_name='Planification (cron)')),
                ('destinataires', models.JSONField(blank=True, default=dict)),
                ('format', models.CharField(
                    choices=[('csv', 'CSV'), ('xlsx', 'XLSX')],
                    default='csv', max_length=10)),
                ('actif', models.BooleanField(
                    default=True, verbose_name='Actif')),
                ('derniere_execution_le', models.DateTimeField(
                    blank=True, null=True, verbose_name='Dernière exécution')),
                ('dernier_statut', models.CharField(
                    blank=True,
                    choices=[('ok', 'Envoyé'),
                             ('non_configure', 'Canal email non configuré'),
                             ('sans_destinataire', 'Aucun destinataire'),
                             ('erreur', 'Erreur')],
                    default='', max_length=20,
                    verbose_name='Dernier statut')),
                ('dernier_detail', models.JSONField(
                    blank=True, default=dict, verbose_name='Dernier détail')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company',
                    verbose_name='Société')),
                ('rapport_def', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='abonnements',
                    to='reporting.rapportdefinition',
                    verbose_name='Rapport')),
            ],
            options={
                'verbose_name': 'Abonnement à un rapport',
                'verbose_name_plural': 'Abonnements à un rapport',
                'ordering': ['-created_at', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='rapportabonnement',
            index=models.Index(
                fields=['company', 'actif'], name='rpt_abonnement_idx'),
        ),
    ]
