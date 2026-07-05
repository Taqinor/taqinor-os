# XKB22 — Parcours de lecture d'intégration (séquences ordonnées d'articles).
# Trois nouvelles tables uniquement : n'affecte aucun article ni assignation
# existante. Réversible par ``git revert`` / ``migrate kb 0018``.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0014_customuser_account_lockout'),
        ('kb', '0018_partagearticlekb'),
    ]

    operations = [
        migrations.CreateModel(
            name='KbParcours',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('nom', models.CharField(
                    max_length=200, verbose_name='Nom du parcours')),
                ('description', models.TextField(
                    blank=True, default='', verbose_name='Description')),
                ('role_cible', models.CharField(
                    blank=True, choices=[
                        ('admin', 'Administrateur'),
                        ('responsable', 'Responsable'),
                        ('normal', 'Utilisateur')],
                    default='', max_length=20,
                    verbose_name='Palier de rôle ciblé')),
                ('metier', models.CharField(
                    blank=True, default='', max_length=120,
                    verbose_name='Métier ciblé')),
                ('actif', models.BooleanField(
                    default=True, verbose_name='Actif')),
                ('date_creation', models.DateTimeField(
                    auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='kb_app_parcours', to='authentication.company',
                    verbose_name='Société')),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='kb_app_parcours_crees',
                    to=settings.AUTH_USER_MODEL, verbose_name='Créé par')),
            ],
            options={
                'verbose_name': 'Parcours de lecture',
                'verbose_name_plural': 'Parcours de lecture',
                'ordering': ['nom', '-id'],
            },
        ),
        migrations.CreateModel(
            name='KbParcoursArticle',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('ordre', models.PositiveIntegerField(
                    default=0, verbose_name='Ordre')),
                ('article', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='parcours_membres', to='kb.kbarticle',
                    verbose_name='Article')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='kb_app_parcours_articles',
                    to='authentication.company', verbose_name='Société')),
                ('parcours', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='articles_ordonnes', to='kb.kbparcours',
                    verbose_name='Parcours')),
            ],
            options={
                'verbose_name': 'Article du parcours',
                'verbose_name_plural': 'Articles du parcours',
                'ordering': ['parcours', 'ordre', 'id'],
                'unique_together': {('parcours', 'article')},
            },
        ),
        migrations.CreateModel(
            name='KbParcoursAssignation',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('date_creation', models.DateTimeField(
                    auto_now_add=True, verbose_name='Assigné le')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='kb_app_parcours_assignations',
                    to='authentication.company', verbose_name='Société')),
                ('parcours', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='assignations', to='kb.kbparcours',
                    verbose_name='Parcours')),
                ('utilisateur', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='kb_app_parcours_assignations',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Utilisateur assigné')),
            ],
            options={
                'verbose_name': 'Assignation de parcours',
                'verbose_name_plural': 'Assignations de parcours',
                'ordering': ['-date_creation', '-id'],
                'unique_together': {('parcours', 'utilisateur')},
            },
        ),
        migrations.AddIndex(
            model_name='kbparcours',
            index=models.Index(
                fields=['company', 'actif'], name='kb_parcours_co_act_idx'),
        ),
        migrations.AddIndex(
            model_name='kbparcoursarticle',
            index=models.Index(
                fields=['company', 'parcours'], name='kb_parcours_art_co_idx'),
        ),
        migrations.AddIndex(
            model_name='kbparcoursassignation',
            index=models.Index(
                fields=['company', 'utilisateur'],
                name='kb_parcours_assign_user_idx'),
        ),
    ]
