# XKB19 — Partage web public d'article (lien tokenisé, opt-in par article).
# Nouvelle table uniquement : n'affecte aucun article existant (aucun article
# n'est exposé publiquement tant qu'un PartageArticleKb n'est pas créé
# explicitement). Réversible par ``git revert`` / ``migrate kb 0017``.
import apps.kb.models
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0014_customuser_account_lockout'),
        ('kb', '0017_kbarticle_langue_traduction'),
    ]

    operations = [
        migrations.CreateModel(
            name='PartageArticleKb',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('token', models.CharField(
                    default=apps.kb.models._default_partage_token,
                    editable=False, max_length=64, unique=True,
                    verbose_name='Jeton')),
                ('expires_at', models.DateTimeField(
                    blank=True, null=True, verbose_name='Expire le')),
                ('actif', models.BooleanField(
                    default=True, verbose_name='Actif')),
                ('consultations', models.PositiveIntegerField(
                    default=0, verbose_name='Consultations')),
                ('date_creation', models.DateTimeField(
                    auto_now_add=True, verbose_name='Créé le')),
                ('article', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='partages', to='kb.kbarticle',
                    verbose_name='Article')),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='kb_app_partages', to='authentication.company',
                    verbose_name='Société')),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='kb_app_partages_crees',
                    to=settings.AUTH_USER_MODEL, verbose_name='Créé par')),
            ],
            options={
                'verbose_name': "Partage public de l'article",
                'verbose_name_plural': "Partages publics d'article",
                'ordering': ['-date_creation', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='partagearticlekb',
            index=models.Index(
                fields=['company', 'article'], name='kb_partage_co_art_idx'),
        ),
    ]
