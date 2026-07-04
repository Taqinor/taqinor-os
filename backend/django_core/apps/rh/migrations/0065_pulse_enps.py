# Generated for XRH32 — baromètre interne eNPS anonyme (pulse survey).

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('rh', '0064_ayantdroit_avantagesocial'),
    ]

    operations = [
        migrations.CreateModel(
            name='CampagnePulse',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('question_enps', models.CharField(
                    default=(
                        'Sur une échelle de 0 à 10, recommanderiez-vous '
                        'notre entreprise comme employeur à un proche ?'),
                    max_length=255, verbose_name='Question eNPS')),
                ('question_libre', models.CharField(
                    blank=True, default='', max_length=255,
                    verbose_name='Question libre')),
                ('date_debut', models.DateField(
                    blank=True, null=True, verbose_name='Date de début')),
                ('date_fin', models.DateField(
                    blank=True, null=True, verbose_name='Date de fin')),
                ('date_creation', models.DateTimeField(
                    auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='rh_campagnes_pulse',
                    to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Campagne pulse',
                'verbose_name_plural': 'Campagnes pulse',
                'ordering': ['-date_creation'],
            },
        ),
        migrations.CreateModel(
            name='ReponsePulse',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('score', models.PositiveSmallIntegerField(
                    verbose_name='Note (0–10)')),
                ('commentaire', models.TextField(
                    blank=True, default='', verbose_name='Commentaire libre')),
                ('date_creation', models.DateTimeField(
                    auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='rh_reponses_pulse',
                    to='authentication.company', verbose_name='Société')),
                ('campagne', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='reponses', to='rh.campagnepulse',
                    verbose_name='Campagne')),
            ],
            options={
                'verbose_name': 'Réponse pulse',
                'verbose_name_plural': 'Réponses pulse',
                'ordering': ['-date_creation'],
            },
        ),
        migrations.AddIndex(
            model_name='reponsepulse',
            index=models.Index(
                fields=['company', 'campagne'],
                name='rh_reppulse_comp_camp_idx'),
        ),
        migrations.CreateModel(
            name='ParticipationPulse',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('token_hash', models.CharField(
                    max_length=64, verbose_name='Jeton (empreinte)')),
                ('date_creation', models.DateTimeField(
                    auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='rh_participations_pulse',
                    to='authentication.company', verbose_name='Société')),
                ('campagne', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='participations', to='rh.campagnepulse',
                    verbose_name='Campagne')),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='participations_pulse',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Utilisateur')),
            ],
            options={
                'verbose_name': 'Participation pulse',
                'verbose_name_plural': 'Participations pulse',
            },
        ),
        migrations.AddConstraint(
            model_name='participationpulse',
            constraint=models.UniqueConstraint(
                fields=['campagne', 'user'],
                name='rh_partpulse_camp_user_uniq'),
        ),
    ]
