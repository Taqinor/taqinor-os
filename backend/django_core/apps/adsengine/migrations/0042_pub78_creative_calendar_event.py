# PUB78 — Calendrier créatif marocain : modèle CreativeCalendarEvent (fenêtres
# saisonnières Ramadan/Aïds/rentrée/canicule/agricole) alimentant le tri du
# backlog par proximité calendaire réelle + les fenêtres de recommandation.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('adsengine', '0041_pub77_creativeasset_language'),
        ('authentication', '0025_company_est_demo_mode_presentation'),
    ]

    operations = [
        migrations.CreateModel(
            name='CreativeCalendarEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tag', models.SlugField(help_text='Clé de saison (ex. ramadan, aid_fitr, rentree, canicule).', max_length=40, verbose_name='Tag saisonnier')),
                ('label', models.CharField(max_length=120, verbose_name='Libellé')),
                ('date_debut', models.DateField(verbose_name='Début')),
                ('date_fin', models.DateField(verbose_name='Fin')),
                ('lead_days', models.PositiveIntegerField(default=30, help_text='Fenêtre de recommandation ouverte J-lead_days avant le début.', verbose_name='Anticipation (jours)')),
                ('market_mode', models.CharField(blank=True, default='', max_length=20, verbose_name='Mode marché (optionnel)')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Événement de calendrier créatif',
                'verbose_name_plural': 'Événements de calendrier créatif',
                'ordering': ['date_debut'],
            },
        ),
        migrations.AddIndex(
            model_name='creativecalendarevent',
            index=models.Index(fields=['company', 'date_debut'], name='adseng_calevent_co_debut_idx'),
        ),
        migrations.AddConstraint(
            model_name='creativecalendarevent',
            constraint=models.UniqueConstraint(fields=['company', 'tag', 'date_debut'], name='uniq_adseng_calevent_co_tag_debut'),
        ),
    ]
