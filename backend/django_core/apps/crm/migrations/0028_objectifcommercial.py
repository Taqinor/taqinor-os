"""FG39 — ObjectifCommercial model (sales objectives / KPI targets).

Additif : nouvelle table, aucune colonne existante modifiée.
Company-scoped via FK ; owner optionnel (FK à CustomUser).
Trois UniqueConstraints conditionnels (un par period_type) avec noms explicites
≤ 30 chars — règle CI-enforced.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0027_appointment'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ObjectifCommercial',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID')),
                ('metric', models.CharField(
                    max_length=20,
                    choices=[
                        ('nb_leads', 'Nombre de leads'),
                        ('nb_contacts', 'Leads contactés'),
                        ('nb_devis', 'Nombre de devis'),
                        ('ca_signe', 'CA signé (MAD TTC)'),
                        ('nb_rdv', 'Rendez-vous effectués'),
                    ],
                    verbose_name='Métrique',
                )),
                ('period_type', models.CharField(
                    max_length=10,
                    choices=[
                        ('month', 'Mensuel'),
                        ('quarter', 'Trimestriel'),
                        ('year', 'Annuel'),
                    ],
                    default='month',
                    verbose_name='Périodicité',
                )),
                ('period_year', models.PositiveSmallIntegerField(
                    verbose_name='Année',
                )),
                ('period_month', models.PositiveSmallIntegerField(
                    null=True, blank=True,
                    verbose_name='Mois (1–12)',
                    help_text='Uniquement pour les objectifs mensuels.',
                )),
                ('period_quarter', models.PositiveSmallIntegerField(
                    null=True, blank=True,
                    verbose_name='Trimestre (1–4)',
                    help_text='Uniquement pour les objectifs trimestriels.',
                )),
                ('cible', models.DecimalField(
                    max_digits=14, decimal_places=2,
                    verbose_name='Cible',
                )),
                ('notes', models.TextField(
                    blank=True, null=True, verbose_name='Notes',
                )),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('date_modification', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='objectifs_commerciaux',
                    to='authentication.company',
                )),
                ('owner', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='crm_objectifs',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Responsable',
                )),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='crm_objectifs_crees',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Créé par',
                )),
            ],
            options={
                'verbose_name': 'Objectif commercial',
                'verbose_name_plural': 'Objectifs commerciaux',
                'ordering': ['-period_year', '-period_month', 'metric'],
            },
        ),
        migrations.AddConstraint(
            model_name='objectifcommercial',
            constraint=models.UniqueConstraint(
                fields=['company', 'owner', 'metric',
                        'period_type', 'period_year', 'period_month'],
                name='crm_obj_uniq_month',
                condition=models.Q(period_type='month'),
            ),
        ),
        migrations.AddConstraint(
            model_name='objectifcommercial',
            constraint=models.UniqueConstraint(
                fields=['company', 'owner', 'metric',
                        'period_type', 'period_year', 'period_quarter'],
                name='crm_obj_uniq_quarter',
                condition=models.Q(period_type='quarter'),
            ),
        ),
        migrations.AddConstraint(
            model_name='objectifcommercial',
            constraint=models.UniqueConstraint(
                fields=['company', 'owner', 'metric',
                        'period_type', 'period_year'],
                name='crm_obj_uniq_year',
                condition=models.Q(period_type='year'),
            ),
        ),
    ]
