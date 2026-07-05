# ODX16 — ``AbonnementMonitoring`` recréé DANS L'ÉTAT de monitoring sur la MÊME
# table physique existante (db_table='compta_abonnementmonitoring') via
# SeparateDatabaseAndState (state-only, aucun SQL). Dépend de compta 0105 qui
# retire le modèle de l'état compta AVANT : ainsi aucun instant n'a deux modèles
# pour la même table. Aucune donnée déplacée.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0014_customuser_account_lockout'),
        ('compta', '0105_odx16_abonnement_monitoring_split'),
        ('monitoring', '0003_cleaningevent'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='AbonnementMonitoring',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('client_id', models.PositiveIntegerField(verbose_name='Id du client')),
                        ('installation_id', models.PositiveIntegerField(blank=True, null=True, verbose_name="Id de l'installation")),
                        ('periodicite', models.CharField(choices=[('mensuel', 'Mensuel'), ('annuel', 'Annuel')], default='mensuel', max_length=8, verbose_name='Périodicité')),
                        ('montant', models.DecimalField(decimal_places=2, default=0, max_digits=12, verbose_name='Montant par période (MAD)')),
                        ('statut', models.CharField(choices=[('actif', 'Actif'), ('suspendu', 'Suspendu'), ('resilie', 'Résilié')], default='actif', max_length=8, verbose_name='Statut')),
                        ('date_debut', models.DateField(blank=True, null=True, verbose_name='Date de début')),
                        ('prochaine_echeance', models.DateField(blank=True, null=True, verbose_name='Prochaine échéance')),
                        ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                        ('derniere_facturation', models.DateField(blank=True, null=True, verbose_name='Dernière période facturée')),
                        ('motif_resiliation', models.CharField(blank=True, default='', max_length=255, verbose_name='Motif de résiliation')),
                        ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='abonnements_monitoring', to='authentication.company', verbose_name='Société')),
                    ],
                    options={
                        'verbose_name': 'Abonnement de monitoring',
                        'verbose_name_plural': 'Abonnements de monitoring',
                        'db_table': 'compta_abonnementmonitoring',
                        'ordering': ['prochaine_echeance', 'id'],
                    },
                ),
            ],
            database_operations=[],
        ),
    ]
