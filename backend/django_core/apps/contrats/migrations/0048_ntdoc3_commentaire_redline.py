"""NTDOC3 — Commentaires par clause / par ligne de diff sur la négociation.

Purement ADDITIF : une seule nouvelle table (``CommentaireRedline``). Aucune
table existante n'est modifiée.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0024_ntprt1_customuser_portee'),
        ('contrats', '0047_ntdoc1_document_contrepartie'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CommentaireRedline',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('ligne_reference', models.PositiveIntegerField(blank=True, null=True, verbose_name='Ligne du diff')),
                ('extrait_ligne', models.CharField(blank=True, default='', max_length=500, verbose_name='Extrait de la ligne')),
                ('contenu', models.TextField(verbose_name='Commentaire')),
                ('resolu', models.BooleanField(default=False, verbose_name='Résolu')),
                ('date_resolution', models.DateTimeField(blank=True, null=True, verbose_name='Résolu le')),
                ('auteur', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='contrats_commentaires_redline', to=settings.AUTH_USER_MODEL, verbose_name='Auteur')),
                ('clause', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='commentaires_redline', to='contrats.clause', verbose_name='Clause visée')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('contrat', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='commentaires_redline', to='contrats.contrat', verbose_name='Contrat')),
                ('document_contrepartie', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='commentaires_redline', to='contrats.documentcontrepartie', verbose_name='Dépôt contrepartie')),
                ('resolu_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='contrats_commentaires_redline_resolus', to=settings.AUTH_USER_MODEL, verbose_name='Résolu par')),
            ],
            options={
                'verbose_name': 'Commentaire de redline',
                'verbose_name_plural': 'Commentaires de redline',
                'ordering': ['contrat_id', 'resolu', 'ligne_reference', 'id'],
                'indexes': [
                    models.Index(fields=['contrat', 'resolu'], name='contrats_cred_ct_resolu'),
                    models.Index(fields=['company', 'resolu'], name='contrats_cred_co_resolu'),
                ],
            },
        ),
    ]
