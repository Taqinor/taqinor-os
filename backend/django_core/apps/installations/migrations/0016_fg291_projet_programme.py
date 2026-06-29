# Generated for FG291 — Programme / Projet multi-chantiers.
# Additif : on AJOUTE quatre tables (Projet + trois tables de liaison), aucune
# colonne d'une table existante n'est modifiée. Aucune migration destructive.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0012_customuser_must_change_password_and_more'),
        ('crm', '0028_objectifcommercial'),
        ('ventes', '0038_fg254_fichetechnique'),
        ('sav', '0010_fg88_ticket_date_tournee'),
        ('installations', '0015_fieldop'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Projet',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reference', models.CharField(max_length=50)),
                ('nom', models.CharField(max_length=200)),
                ('site_adresse', models.TextField(blank=True, null=True)),
                ('site_ville', models.CharField(blank=True, max_length=120, null=True)),
                ('statut', models.CharField(choices=[('brouillon', 'Brouillon'), ('actif', 'Actif'), ('en_pause', 'En pause'), ('termine', 'Terminé'), ('annule', 'Annulé')], default='brouillon', max_length=12)),
                ('description', models.TextField(blank=True, null=True)),
                ('date_debut', models.DateField(blank=True, null=True)),
                ('date_fin_cible', models.DateField(blank=True, null=True)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('date_modification', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='installations_projets', to='authentication.company')),
                ('client', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='installations_projets', to='crm.client')),
                ('responsable', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installations_projets_responsable', to=settings.AUTH_USER_MODEL)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installations_projets_crees', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Programme / Projet',
                'verbose_name_plural': 'Programmes / Projets',
                'ordering': ['-date_creation'],
            },
        ),
        migrations.CreateModel(
            name='ProjetChantier',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('libelle', models.CharField(blank=True, max_length=120, null=True)),
                ('ordre', models.PositiveIntegerField(default=0)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='installations_projet_chantiers', to='authentication.company')),
                ('projet', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='chantiers', to='installations.projet')),
                ('installation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='projets', to='installations.installation')),
            ],
            options={
                'verbose_name': 'Chantier de programme',
                'verbose_name_plural': 'Chantiers de programme',
                'ordering': ['projet_id', 'ordre', 'id'],
            },
        ),
        migrations.CreateModel(
            name='ProjetDevis',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='installations_projet_devis', to='authentication.company')),
                ('projet', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='devis', to='installations.projet')),
                ('devis', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='installations_projets', to='ventes.devis')),
            ],
            options={
                'verbose_name': 'Devis de programme',
                'verbose_name_plural': 'Devis de programme',
                'ordering': ['projet_id', 'id'],
            },
        ),
        migrations.CreateModel(
            name='ProjetTicket',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='installations_projet_tickets', to='authentication.company')),
                ('projet', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tickets', to='installations.projet')),
                ('ticket', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='installations_projets', to='sav.ticket')),
            ],
            options={
                'verbose_name': 'Ticket de programme',
                'verbose_name_plural': 'Tickets de programme',
                'ordering': ['projet_id', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='projet',
            index=models.Index(fields=['company', 'statut'], name='idx_projet_co_statut'),
        ),
        migrations.AddIndex(
            model_name='projetchantier',
            index=models.Index(fields=['company', 'projet'], name='idx_projchant_co_proj'),
        ),
        migrations.AddIndex(
            model_name='projetdevis',
            index=models.Index(fields=['company', 'projet'], name='idx_projdevis_co_proj'),
        ),
        migrations.AddIndex(
            model_name='projetticket',
            index=models.Index(fields=['company', 'projet'], name='idx_projticket_co_proj'),
        ),
        migrations.AlterUniqueTogether(
            name='projet',
            unique_together={('company', 'reference')},
        ),
        migrations.AlterUniqueTogether(
            name='projetchantier',
            unique_together={('projet', 'installation')},
        ),
        migrations.AlterUniqueTogether(
            name='projetdevis',
            unique_together={('projet', 'devis')},
        ),
        migrations.AlterUniqueTogether(
            name='projetticket',
            unique_together={('projet', 'ticket')},
        ),
    ]
