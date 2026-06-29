# Generated 2026-06-29 — FG169 Planning d'équipes / roster (shifts)

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0012_customuser_must_change_password_and_more"),
        ("rh", "0010_heuressupp"),
    ]

    operations = [
        migrations.CreateModel(
            name='AffectationRoster',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID')),
                ('equipe', models.CharField(
                    max_length=120, verbose_name='Équipe')),
                ('vehicule_id', models.PositiveIntegerField(
                    blank=True, null=True,
                    verbose_name='Camionnette (ID, optionnel)')),
                ('date', models.DateField(verbose_name="Date d'affectation")),
                ('semaine_du', models.DateField(
                    blank=True, null=True,
                    verbose_name='Semaine du (lundi)')),
                ('creneau', models.CharField(
                    choices=[
                        ('journee', 'Journée'),
                        ('matin', 'Matin'),
                        ('apres_midi', 'Après-midi'),
                    ],
                    default='journee', max_length=10,
                    verbose_name='Créneau')),
                ('conflit_conge', models.BooleanField(
                    default=False, verbose_name='Conflit de congé')),
                ('note', models.CharField(
                    blank=True, default='', max_length=255,
                    verbose_name='Note')),
                ('date_creation', models.DateTimeField(
                    auto_now_add=True, verbose_name='Créé le')),
                ('date_modification', models.DateTimeField(
                    auto_now=True, verbose_name='Modifié le')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='rh_affectations_roster',
                    to='authentication.company',
                    verbose_name='Société')),
                ('employe', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='affectations_roster',
                    to='rh.dossieremploye',
                    verbose_name='Employé')),
            ],
            options={
                'verbose_name': 'Affectation roster',
                'verbose_name_plural': 'Affectations roster',
                'ordering': ['-date', 'equipe', 'employe'],
            },
        ),
        migrations.AddIndex(
            model_name='affectationroster',
            index=models.Index(
                fields=['company', 'semaine_du'],
                name='rh_roster_comp_semaine_idx'),
        ),
        migrations.AddIndex(
            model_name='affectationroster',
            index=models.Index(
                fields=['company', 'equipe'],
                name='rh_roster_comp_equipe_idx'),
        ),
        migrations.AddIndex(
            model_name='affectationroster',
            index=models.Index(
                fields=['company', 'date'],
                name='rh_roster_comp_date_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='affectationroster',
            unique_together={('company', 'employe', 'date')},
        ),
    ]
