"""AUD121 — table de session d'import de relevé bancaire (dry-run jetonné).

ADDITIVE ONLY : crée la seule table ``ventes_releveimportsession``. Aucune
table ni colonne existante n'est touchée, aucune donnée déplacée —
``git revert`` suffit à revenir en arrière.

Elle porte la liste COMPLÈTE des décisions de rapprochement d'un dry-run,
son jeton à usage unique et le SHA-256 du fichier (déduplication du
double-import). Voir ``apps/ventes/models_releve.py`` pour le pourquoi.

Multi-tenancy : ``company`` obligatoire (TenantModel), forcée côté vue —
jamais lue du corps de la requête.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('ventes', '0112_aud422_rls_argent'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReleveImportSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('token', models.CharField(max_length=64, unique=True)),
                ('fichier_hash', models.CharField(db_index=True,
                                                  max_length=64)),
                ('fichier_nom', models.CharField(blank=True, default='',
                                                 max_length=255)),
                ('decisions', models.JSONField(blank=True, default=list)),
                ('consomme_at', models.DateTimeField(blank=True, null=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company',
                    verbose_name='Société')),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='releve_import_sessions',
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': "Session d'import de relevé",
                'verbose_name_plural': "Sessions d'import de relevé",
                'db_table': 'ventes_releveimportsession',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='releveimportsession',
            index=models.Index(fields=['company', 'fichier_hash'],
                               name='idx_relevesess_co_hash'),
        ),
    ]
