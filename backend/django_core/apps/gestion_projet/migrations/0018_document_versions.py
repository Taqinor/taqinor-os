# Generated for PROJ33 -- Documents & plans versionnés.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0012_customuser_must_change_password_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('gestion_projet', '0017_compterendureunion'),
    ]

    operations = [
        migrations.CreateModel(
            name='DocumentProjet',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom', models.CharField(max_length=200, verbose_name='Nom')),
                ('type_doc', models.CharField(choices=[('plan', 'Plan'), ('note', 'Note de calcul'), ('photo', 'Photo'), ('contrat', 'Contrat'), ('pv', 'Procès-verbal'), ('autre', 'Autre')], default='autre', max_length=10, verbose_name='Type de document')),
                ('description', models.TextField(blank=True, default='', verbose_name='Description')),
                ('derniere_version', models.PositiveIntegerField(default=0, verbose_name='Dernière version')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gestion_projet_documents', to='authentication.company', verbose_name='Société')),
                ('projet', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='documents', to='gestion_projet.projet', verbose_name='Projet')),
            ],
            options={
                'verbose_name': 'Document projet',
                'verbose_name_plural': 'Documents projet',
                'ordering': ['projet', 'nom', 'id'],
                'indexes': [models.Index(fields=['projet', 'type_doc'], name='gp_doc_proj_type_idx')],
            },
        ),
        migrations.CreateModel(
            name='VersionDocument',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('version', models.PositiveIntegerField(verbose_name='Version')),
                ('fichier', models.FileField(upload_to='gestion_projet/documents/', verbose_name='Fichier')),
                ('commentaire', models.TextField(blank=True, default='', verbose_name='Commentaire de révision')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('auteur', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='gestion_projet_versions_doc', to=settings.AUTH_USER_MODEL, verbose_name='Auteur')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gestion_projet_versions_doc', to='authentication.company', verbose_name='Société')),
                ('document', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='versions', to='gestion_projet.documentprojet', verbose_name='Document')),
            ],
            options={
                'verbose_name': 'Version de document',
                'verbose_name_plural': 'Versions de document',
                'ordering': ['document', '-version', '-id'],
                'unique_together': {('document', 'version')},
                'indexes': [models.Index(fields=['document', '-version'], name='gp_docver_doc_idx')],
            },
        ),
    ]
