"""NTDOC11 — création du module ``datarooms`` : salles de données.

Migration ADDITIVE (deux nouvelles tables, aucune donnée existante touchée).
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0032_customuser_calendrier_hegirien'),
        ('ged', '0045_ntdoc10_empreinte_certificat'),
    ]

    operations = [
        migrations.CreateModel(
            name='SalleDeDonnees',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('nom', models.CharField(max_length=255,
                                         verbose_name='Nom')),
                ('description', models.TextField(
                    blank=True, default='', verbose_name='Description')),
                ('deal_type', models.CharField(
                    blank=True, default='', max_length=120,
                    verbose_name="Type d'opération")),
                ('statut', models.CharField(
                    choices=[('ouverte', 'Ouverte'), ('fermee', 'Fermée')],
                    default='ouverte', max_length=10,
                    verbose_name='Statut')),
                ('expires_at', models.DateTimeField(
                    blank=True, null=True, verbose_name='Expire le')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='salles_donnees_creees',
                    to=settings.AUTH_USER_MODEL, verbose_name='Créée par')),
                ('dossier_source', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='salles_donnees', to='ged.folder',
                    verbose_name='Dossier GED de départ')),
            ],
            options={
                'verbose_name': 'Salle de données',
                'verbose_name_plural': 'Salles de données',
                'ordering': ['-created_at', '-id'],
            },
        ),
        migrations.CreateModel(
            name='SalleDeDonneesDocument',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('ordre', models.PositiveIntegerField(
                    default=0, verbose_name="Ordre d'affichage")),
                ('visible', models.BooleanField(
                    default=True, verbose_name='Visible')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
                ('document', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='appartenances_salle', to='ged.document',
                    verbose_name='Document')),
                ('salle', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='documents', to='datarooms.sallededonnees',
                    verbose_name='Salle')),
            ],
            options={
                'verbose_name': 'Document de salle de données',
                'verbose_name_plural': 'Documents de salle de données',
                'ordering': ['ordre', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='sallededonnees',
            index=models.Index(fields=['company', 'statut'],
                               name='dataroom_co_statut_idx'),
        ),
        migrations.AddConstraint(
            model_name='sallededonneesdocument',
            constraint=models.UniqueConstraint(
                fields=('salle', 'document'),
                name='dataroom_uniq_salle_document'),
        ),
    ]
