# Generated for FG297 — Contrôle documentaire de projet (plans & révisions).
# Additive: two new tables, no column altered.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0012_customuser_must_change_password_and_more'),
        ('installations', '0013_modeleprojet_modeleprojetbomligne_modeleprojetjalon_and_more'),
        ('records', '0003_attachment_phase'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='DocumentProjet',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name='ID',
                    ),
                ),
                (
                    'type_doc',
                    models.CharField(
                        choices=[
                            ('schema_unifilaire', 'Schéma unifilaire'),
                            ('calepinage', 'Calepinage'),
                            ('note_calcul', 'Note de calcul'),
                            ('autre', 'Autre'),
                        ],
                        default='autre',
                        max_length=20,
                    ),
                ),
                ('titre', models.CharField(max_length=200)),
                ('notes', models.TextField(blank=True, null=True)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('date_modification', models.DateTimeField(auto_now=True)),
                (
                    'company',
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='inst_documents_projet',
                        to='authentication.company',
                    ),
                ),
                (
                    'installation',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='inst_documents',
                        to='installations.installation',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Document de projet',
                'verbose_name_plural': 'Documents de projet',
                'ordering': ['installation_id', 'type_doc', 'titre'],
            },
        ),
        migrations.AddIndex(
            model_name='documentprojet',
            index=models.Index(
                fields=['company', 'installation'],
                name='inst_docproj_co_inst_idx',
            ),
        ),
        migrations.CreateModel(
            name='RevisionDocument',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name='ID',
                    ),
                ),
                ('indice', models.CharField(default='A', max_length=10)),
                ('date_revision', models.DateField()),
                ('notes', models.TextField(blank=True, null=True)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                (
                    'auteur',
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='inst_revisions_document_auteur',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'company',
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='inst_revisions_document',
                        to='authentication.company',
                    ),
                ),
                (
                    'document',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='inst_revisions',
                        to='installations.documentprojet',
                    ),
                ),
                (
                    'fichier',
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='inst_revisions_document',
                        to='records.attachment',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Révision de document',
                'verbose_name_plural': 'Révisions de document',
                'ordering': ['document_id', '-date_revision', '-date_creation'],
            },
        ),
        migrations.AddIndex(
            model_name='revisiondocument',
            index=models.Index(
                fields=['company', 'document'],
                name='inst_revdoc_co_doc_idx',
            ),
        ),
        migrations.AddConstraint(
            model_name='revisiondocument',
            constraint=models.UniqueConstraint(
                fields=['document', 'indice'],
                name='inst_revdoc_doc_indice_uniq',
            ),
        ),
    ]
