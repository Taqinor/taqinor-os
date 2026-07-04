# ZGED12 — Presse-papiers Knowledge (blocs de texte réutilisables). Nouvelle
# table uniquement : n'affecte aucun article existant. Réversible par
# ``git revert`` / ``migrate kb 0021``.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0014_customuser_account_lockout'),
        ('kb', '0021_kbarticle_proprietes'),
    ]

    operations = [
        migrations.CreateModel(
            name='BlocReutilisable',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('nom', models.CharField(
                    max_length=200, verbose_name='Nom du bloc')),
                ('corps', models.TextField(
                    blank=True, default='',
                    verbose_name='Corps (texte/markdown léger)')),
                ('portee', models.CharField(
                    choices=[('personnel', 'Personnel'),
                             ('societe', 'Société')],
                    default='personnel', max_length=10,
                    verbose_name='Portée')),
                ('date_creation', models.DateTimeField(
                    auto_now_add=True, verbose_name='Créé le')),
                ('date_modification', models.DateTimeField(
                    auto_now=True, verbose_name='Modifié le')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='kb_app_blocs', to='authentication.company',
                    verbose_name='Société')),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='kb_app_blocs_crees',
                    to=settings.AUTH_USER_MODEL, verbose_name='Créé par')),
            ],
            options={
                'verbose_name': 'Bloc réutilisable',
                'verbose_name_plural': 'Blocs réutilisables',
                'ordering': ['nom', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='blocreutilisable',
            index=models.Index(
                fields=['company', 'portee'], name='kb_bloc_co_portee_idx'),
        ),
    ]
