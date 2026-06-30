# Generated for PROJ30 -- Registre des risques.

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0012_customuser_must_change_password_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('gestion_projet', '0014_timesheet'),
    ]

    operations = [
        migrations.CreateModel(
            name='Risque',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('libelle', models.CharField(max_length=200, verbose_name='Libellé')),
                ('description', models.TextField(blank=True, default='', verbose_name='Description')),
                ('categorie', models.CharField(choices=[('technique', 'Technique'), ('delai', 'Délai'), ('cout', 'Coût'), ('fournisseur', 'Fournisseur'), ('reglementaire', 'Réglementaire'), ('securite', 'Sécurité'), ('autre', 'Autre')], default='autre', max_length=14, verbose_name='Catégorie')),
                ('probabilite', models.PositiveSmallIntegerField(default=1, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)], verbose_name='Probabilité (1–5)')),
                ('impact', models.PositiveSmallIntegerField(default=1, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)], verbose_name='Impact (1–5)')),
                ('criticite', models.PositiveSmallIntegerField(default=1, verbose_name='Criticité (1–25)')),
                ('statut', models.CharField(choices=[('ouvert', 'Ouvert'), ('surveille', 'Surveillé'), ('maitrise', 'Maîtrisé'), ('clos', 'Clos')], default='ouvert', max_length=10, verbose_name='Statut')),
                ('mitigation', models.TextField(blank=True, default='', verbose_name='Plan de mitigation')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gestion_projet_risques', to='authentication.company', verbose_name='Société')),
                ('projet', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='risques', to='gestion_projet.projet', verbose_name='Projet')),
                ('proprietaire', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='gestion_projet_risques', to=settings.AUTH_USER_MODEL, verbose_name='Propriétaire')),
            ],
            options={
                'verbose_name': 'Risque',
                'verbose_name_plural': 'Risques',
                'ordering': ['-criticite', '-id'],
                'indexes': [models.Index(fields=['projet', '-criticite'], name='gp_risque_proj_crit_idx')],
            },
        ),
    ]
