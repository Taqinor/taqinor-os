# Generated for XPRJ1 -- Timesheet approval workflow + period lock.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0012_customuser_must_change_password_and_more'),
        ('gestion_projet', '0022_soustraitance_cloture'),
    ]

    operations = [
        migrations.AddField(
            model_name='timesheet',
            name='statut',
            field=models.CharField(
                choices=[
                    ('brouillon', 'Brouillon'),
                    ('soumise', 'Soumise'),
                    ('approuvee', 'Approuvée'),
                    ('rejetee', 'Rejetée'),
                ],
                default='brouillon', max_length=10, verbose_name='Statut'),
        ),
        migrations.AddField(
            model_name='timesheet',
            name='saisi_par',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='gestion_projet_timesheets_saisies',
                to=settings.AUTH_USER_MODEL, verbose_name='Saisi par'),
        ),
        migrations.AddField(
            model_name='timesheet',
            name='approuve_par',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='gestion_projet_timesheets_approuvees',
                to=settings.AUTH_USER_MODEL, verbose_name='Approuvé par'),
        ),
        migrations.AddField(
            model_name='timesheet',
            name='date_approbation',
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="Date d'approbation"),
        ),
        migrations.AddField(
            model_name='timesheet',
            name='motif_rejet',
            field=models.CharField(
                blank=True, default='', max_length=255,
                verbose_name='Motif de rejet'),
        ),
        migrations.AddIndex(
            model_name='timesheet',
            index=models.Index(
                fields=['company', 'statut'], name='gp_ts_co_statut_idx'),
        ),
        migrations.CreateModel(
            name='PeriodeVerrouilleeTemps',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('mois', models.DateField(
                    verbose_name='Mois verrouillé (1er jour du mois)')),
                ('date_creation', models.DateTimeField(
                    auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='gestion_projet_periodes_verrouillees',
                    to='authentication.company', verbose_name='Société')),
                ('verrouille_par', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='gestion_projet_periodes_verrouillees',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Verrouillé par')),
            ],
            options={
                'verbose_name': 'Période verrouillée (temps)',
                'verbose_name_plural': 'Périodes verrouillées (temps)',
                'ordering': ['-mois'],
            },
        ),
        migrations.AddConstraint(
            model_name='periodeverrouilleetemps',
            constraint=models.UniqueConstraint(
                fields=('company', 'mois'),
                name='gp_periode_verr_co_mois_uniq'),
        ),
    ]
