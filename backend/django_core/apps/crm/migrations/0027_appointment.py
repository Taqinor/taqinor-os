"""QJ20 — crm.Appointment model (site-visit scheduler).

Additif : nouvelle table, aucune colonne existante modifiée.
Company-scoped via FK + related_name ; BigAutoField par défaut (projet).
"""

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0026_lead_score'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Appointment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('scheduled_at', models.DateTimeField(
                    verbose_name='Date et heure planifiées',
                    help_text="Heure UTC ; affichée en Africa/Casablanca dans l'UI.",
                )),
                ('statut', models.CharField(
                    max_length=10,
                    choices=[
                        ('planifie', 'Planifié'),
                        ('confirme', 'Confirmé'),
                        ('effectue', 'Effectué'),
                        ('annule', 'Annulé'),
                    ],
                    default='planifie',
                    verbose_name='Statut',
                )),
                ('notes', models.TextField(
                    blank=True, null=True, verbose_name='Notes de visite')),
                ('reminder_sent', models.BooleanField(
                    default=False, verbose_name='Rappel envoyé')),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('date_modification', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='appointments',
                    to='authentication.company',
                )),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='appointments_crees',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Créé par',
                )),
                ('lead', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='appointments',
                    to='crm.lead',
                    verbose_name='Lead',
                )),
            ],
            options={
                'verbose_name': 'Rendez-vous',
                'verbose_name_plural': 'Rendez-vous',
                'ordering': ['scheduled_at'],
            },
        ),
        migrations.AddIndex(
            model_name='appointment',
            index=models.Index(
                fields=['company', 'scheduled_at'],
                name='crm_appt_co_sched_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='appointment',
            index=models.Index(
                fields=['lead', 'statut'],
                name='crm_appt_lead_stat_idx',
            ),
        ),
    ]
