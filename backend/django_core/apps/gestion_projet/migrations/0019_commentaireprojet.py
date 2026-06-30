# Generated for PROJ34 -- Commentaires & @mentions.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0012_customuser_must_change_password_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('gestion_projet', '0018_document_versions'),
    ]

    operations = [
        migrations.CreateModel(
            name='CommentaireProjet',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cible_type', models.CharField(choices=[('projet', 'Projet'), ('tache', 'Tâche'), ('risque', 'Risque'), ('action', 'Action'), ('jalon', 'Jalon'), ('document', 'Document')], default='projet', max_length=10, verbose_name='Type de cible')),
                ('cible_id', models.PositiveIntegerField(blank=True, null=True, verbose_name='ID de la cible')),
                ('texte', models.TextField(verbose_name='Texte')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('auteur', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='gestion_projet_commentaires', to=settings.AUTH_USER_MODEL, verbose_name='Auteur')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gestion_projet_commentaires', to='authentication.company', verbose_name='Société')),
                ('mentions', models.ManyToManyField(blank=True, related_name='gestion_projet_mentions', to=settings.AUTH_USER_MODEL, verbose_name='Personnes mentionnées')),
                ('projet', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='commentaires', to='gestion_projet.projet', verbose_name='Projet')),
            ],
            options={
                'verbose_name': 'Commentaire projet',
                'verbose_name_plural': 'Commentaires projet',
                'ordering': ['-date_creation', '-id'],
                'indexes': [models.Index(fields=['projet', 'cible_type', 'cible_id'], name='gp_comm_proj_cible_idx')],
            },
        ),
    ]
