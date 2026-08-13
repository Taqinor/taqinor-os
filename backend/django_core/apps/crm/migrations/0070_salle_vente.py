# NTCRM17/18 — Salle de vente digitale (Digital Sales Room) : trois nouveaux
# modèles additifs (SalleVente, SalleVenteItem, SalleVenteVue). Aucune
# modification de modèle existant.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import apps.crm.models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('crm', '0069_client_derniere_alerte_dormance'),
    ]

    operations = [
        migrations.CreateModel(
            name='SalleVente',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True,
                                        serialize=False, verbose_name='ID')),
                ('titre', models.CharField(max_length=200, verbose_name='Titre')),
                ('token', models.CharField(
                    default=apps.crm.models._default_salle_vente_token,
                    editable=False, max_length=64, unique=True)),
                ('expires_at', models.DateTimeField(
                    default=apps.crm.models._default_salle_vente_expiry,
                    verbose_name='Expire le')),
                ('password_hash', models.TextField(blank=True, default='')),
                ('actif', models.BooleanField(
                    default=True,
                    help_text='Décoché = révocation immédiate du lien public.',
                    verbose_name='Actif')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('client', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name='salles_vente', to='crm.client')),
                ('company', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name='salles_vente', to='authentication.company')),
                ('created_by', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='salles_vente_creees', to=settings.AUTH_USER_MODEL)),
                ('lead', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name='salles_vente', to='crm.lead')),
            ],
            options={
                'verbose_name': 'Salle de vente',
                'verbose_name_plural': 'Salles de vente',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='sallevente',
            index=models.Index(fields=['token'], name='crm_salle_vente_token_idx'),
        ),
        migrations.CreateModel(
            name='SalleVenteItem',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True,
                                        serialize=False, verbose_name='ID')),
                ('type', models.CharField(choices=[
                    ('devis', 'Devis'), ('document', 'Document'),
                    ('video_lien', 'Lien vidéo'), ('note', 'Note')], max_length=12)),
                ('reference', models.CharField(
                    blank=True, default='', max_length=500,
                    help_text="Id du devis/document GED cible, ou URL/texte "
                              "libre (video_lien/note).")),
                ('titre', models.CharField(blank=True, default='', max_length=200)),
                ('ordre', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('salle', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='items', to='crm.sallevente')),
            ],
            options={
                'verbose_name': 'Élément de salle de vente',
                'verbose_name_plural': 'Éléments de salle de vente',
                'ordering': ['ordre', 'id'],
            },
        ),
        migrations.CreateModel(
            name='SalleVenteVue',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True,
                                        serialize=False, verbose_name='ID')),
                ('ip_hash', models.CharField(blank=True, default='', max_length=64)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('salle', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='vues', to='crm.sallevente')),
            ],
            options={
                'verbose_name': 'Vue de salle de vente',
                'verbose_name_plural': 'Vues de salle de vente',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='salleventevue',
            index=models.Index(fields=['salle', '-created_at'], name='crm_salle_vue_salle_idx'),
        ),
    ]
