# NTDMO14 — visites guidées (product tours) : catalogue d'étapes + suivi par
# utilisateur.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0025_company_est_demo_mode_presentation'),
        ('onboarding', '0003_wire_premier_chantier_event'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProductTourStep',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tour_key', models.SlugField(max_length=60)),
                ('ordre', models.PositiveIntegerField(default=10)),
                ('selecteur', models.CharField(blank=True, default='', max_length=255)),
                ('titre', models.CharField(max_length=200)),
                ('texte', models.TextField()),
                ('ecran_cible', models.CharField(max_length=255)),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='onboarding_tour_steps', to='authentication.company')),
            ],
            options={
                'verbose_name': 'Étape de visite guidée',
                'verbose_name_plural': 'Étapes de visite guidée',
                'ordering': ['tour_key', 'ordre'],
            },
        ),
        migrations.CreateModel(
            name='TourProgress',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tour_key', models.SlugField(max_length=60)),
                ('vu_le', models.DateTimeField(blank=True, null=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='onboarding_tour_progress', to='authentication.company')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='onboarding_tour_progress', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Avancement visite guidée',
                'verbose_name_plural': 'Avancements visite guidée',
                'unique_together': {('user', 'tour_key')},
            },
        ),
        migrations.AlterUniqueTogether(
            name='producttourstep',
            unique_together={('tour_key', 'ordre')},
        ),
    ]
