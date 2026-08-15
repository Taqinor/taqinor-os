# NTAI24 — Index sémantique cross-module (magasin pgvector unifié).
#
# CHAÎNE DE MIGRATIONS : enchaîne EXPLICITEMENT sur la dernière migration de
# `core` et ne dépend d'`authentication` que par la migration qui CRÉE
# `Company` — d'autres lanes ajoutent des migrations à `authentication` en
# parallèle, et une dépendance sur sa tête entrerait en collision.
import django.db.models.deletion
import pgvector.django.vector
from django.db import migrations, models
from pgvector.django import VectorExtension


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0003_company_alter_customuser_groups_and_more'),
        ('core', '0043_ntext17_vue_defaut_index'),
    ]

    operations = [
        # Garantit l'extension pgvector AVANT la colonne `vector` : les
        # migrations de `core` peuvent tourner avant celles de la GED (qui la
        # crée déjà). Idempotent — CREATE EXTENSION IF NOT EXISTS.
        VectorExtension(),
        migrations.CreateModel(
            name='SearchChunk',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('content_type', models.CharField(help_text='Libellé du modèle source, ex. « crm.lead » (jamais une FK vers une app métier).', max_length=60)),
                ('object_id', models.PositiveBigIntegerField(help_text="Identifiant de l'objet source dans son app.")),
                ('module', models.CharField(blank=True, default='', help_text='Module propriétaire (app_label) — permet de restreindre une recherche à un périmètre.', max_length=60)),
                ('titre', models.CharField(blank=True, default='', max_length=255)),
                ('extrait', models.TextField(blank=True, default='')),
                ('embedding', pgvector.django.vector.VectorField(blank=True, dimensions=1024, null=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Fiche indexée (recherche sémantique)',
                'verbose_name_plural': 'Fiches indexées (recherche sémantique)',
                'ordering': ['content_type', 'object_id'],
                'indexes': [models.Index(fields=['company', 'module'], name='core_searchchunk_co_mod_idx')],
                'constraints': [models.UniqueConstraint(fields=('company', 'content_type', 'object_id'), name='uniq_searchchunk_co_ct_obj')],
            },
        ),
    ]
