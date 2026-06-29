# Generated for FG292 — Tâches & sous-tâches de projet avec dépendances.
# Additif : on AJOUTE une table (ProjetTache). Aucune colonne d'une table
# existante n'est modifiée. Aucune migration destructive.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0012_customuser_must_change_password_and_more'),
        ('installations', '0016_fg291_projet_programme'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ProjetTache',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('libelle', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True, null=True)),
                ('date_echeance', models.DateField(blank=True, null=True)),
                ('statut', models.CharField(choices=[('a_faire', 'À faire'), ('en_cours', 'En cours'), ('termine', 'Terminé')], default='a_faire', max_length=10)),
                ('ordre', models.PositiveIntegerField(default=0)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('date_modification', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='installations_projet_taches', to='authentication.company')),
                ('projet', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='taches', to='installations.projet')),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='sous_taches', to='installations.projettache')),
                ('predecesseur', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='suivantes', to='installations.projettache')),
                ('assigne', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installations_taches_assignees', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Tâche de projet',
                'verbose_name_plural': 'Tâches de projet',
                'ordering': ['projet_id', 'ordre', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='projettache',
            index=models.Index(fields=['company', 'projet'], name='idx_projtache_co_proj'),
        ),
        migrations.AddIndex(
            model_name='projettache',
            index=models.Index(fields=['company', 'statut'], name='idx_projtache_co_stat'),
        ),
    ]
