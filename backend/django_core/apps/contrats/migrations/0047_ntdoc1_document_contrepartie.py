"""NTDOC1 — Dépôt de la version « contrepartie » sur un contrat.

Purement ADDITIF : deux nouvelles tables (``LienDepotContrepartie``,
``DocumentContrepartie``). Aucune table existante n'est modifiée — le contenu
figé d'une ``VersionContrat`` (CONTRAT18) reste intouché.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import apps.contrats.models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0024_ntprt1_customuser_portee'),
        ('contrats', '0046_aud509_protect_preuves_contrat'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='LienDepotContrepartie',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('token', models.CharField(default=apps.contrats.models._default_depot_contrepartie_token, editable=False, max_length=64, unique=True, verbose_name='Jeton de dépôt')),
                ('destinataire_nom', models.CharField(blank=True, default='', max_length=200, verbose_name='Nom de la contrepartie')),
                ('destinataire_email', models.EmailField(blank=True, default='', max_length=254, verbose_name='Email de la contrepartie')),
                ('expires_at', models.DateTimeField(blank=True, null=True, verbose_name='Expire le')),
                ('actif', models.BooleanField(default=True, verbose_name='Actif')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('contrat', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='liens_depot_contrepartie', to='contrats.contrat', verbose_name='Contrat')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='contrats_liens_depot_crees', to=settings.AUTH_USER_MODEL, verbose_name='Créé par')),
            ],
            options={
                'verbose_name': 'Lien de dépôt contrepartie',
                'verbose_name_plural': 'Liens de dépôt contrepartie',
                'ordering': ['-id'],
                'indexes': [models.Index(fields=['company', 'contrat'], name='contrats_liendepot_co_ct')],
            },
        ),
        migrations.CreateModel(
            name='DocumentContrepartie',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('fichier_key', models.CharField(blank=True, default='', max_length=512, verbose_name='Clé du fichier')),
                ('nom_fichier', models.CharField(blank=True, default='', max_length=255, verbose_name='Nom du fichier')),
                ('mime', models.CharField(blank=True, default='', max_length=120, verbose_name='Type MIME')),
                ('taille', models.PositiveIntegerField(default=0, verbose_name='Taille (octets)')),
                ('depose_par_nom', models.CharField(blank=True, default='', max_length=200, verbose_name='Déposé par (nom)')),
                ('depose_par_email', models.EmailField(blank=True, default='', max_length=254, verbose_name='Déposé par (email)')),
                ('date_depot', models.DateTimeField(auto_now_add=True, verbose_name='Déposé le')),
                ('statut', models.CharField(choices=[('nouveau', 'Nouveau'), ('en_revue', 'En revue'), ('traite', 'Traité')], default='nouveau', max_length=20, verbose_name='Statut')),
                ('archive', models.BooleanField(default=False, verbose_name='Archivé')),
                ('date_archivage', models.DateTimeField(blank=True, null=True, verbose_name='Archivé le')),
                ('commentaire', models.TextField(blank=True, default='', verbose_name='Commentaire')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('contrat', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='documents_contrepartie', to='contrats.contrat', verbose_name='Contrat')),
                ('depose_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='contrats_depots_contrepartie', to=settings.AUTH_USER_MODEL, verbose_name='Déposé par (compte)')),
                ('lien', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='depots', to='contrats.liendepotcontrepartie', verbose_name='Lien de dépôt')),
            ],
            options={
                'verbose_name': 'Document contrepartie',
                'verbose_name_plural': 'Documents contrepartie',
                'ordering': ['-date_depot', '-id'],
                'indexes': [
                    models.Index(fields=['contrat', '-date_depot'], name='contrats_dcp_ct_date'),
                    models.Index(fields=['company', 'statut'], name='contrats_dcp_co_statut'),
                ],
            },
        ),
    ]
