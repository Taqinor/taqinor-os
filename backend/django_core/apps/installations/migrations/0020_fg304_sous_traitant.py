# Generated for FG304 — Référentiel des sous-traitants chantier.
# Additif : on AJOUTE une seule table (SousTraitant). Aucune colonne d'une table
# existante n'est modifiée. Aucune migration destructive.
#
# SousTraitant référence authentication.Company (la société, multi-tenant) et
# l'utilisateur (created_by, swappable). Aucun lien stock : un sous-traitant est
# DISTINCT d'un fournisseur de matériel.
# Noms d'index ≤ 30 caractères (contrainte Django/Postgres).

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0013_customuser_poste_ref'),
        ('installations', '0019_fg302_indisponibilite_ressource'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SousTraitant',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('raison_sociale', models.CharField(max_length=255)),
                ('metier', models.CharField(choices=[('terrassement', 'Terrassement'), ('genie_civil', 'Génie civil'), ('electricite', 'Électricité'), ('levage', 'Levage'), ('transport', 'Transport'), ('autre', 'Autre')], default='autre', max_length=20)),
                ('contact_nom', models.CharField(blank=True, max_length=255, null=True)),
                ('telephone', models.CharField(blank=True, max_length=40, null=True)),
                ('email', models.EmailField(blank=True, max_length=254, null=True)),
                ('ice', models.CharField(blank=True, max_length=32, null=True)),
                ('rib', models.CharField(blank=True, max_length=34, null=True)),
                ('adresse', models.TextField(blank=True, null=True)),
                ('actif', models.BooleanField(default=True)),
                ('note', models.TextField(blank=True, null=True)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('date_modification', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='installations_sous_traitants', to='authentication.company')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installations_sous_traitants_crees', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Sous-traitant',
                'verbose_name_plural': 'Sous-traitants',
                'ordering': ['raison_sociale'],
            },
        ),
        migrations.AddIndex(
            model_name='soustraitant',
            index=models.Index(fields=['company', 'metier'], name='idx_soustrait_co_metier'),
        ),
        migrations.AddIndex(
            model_name='soustraitant',
            index=models.Index(fields=['company', 'actif'], name='idx_soustrait_co_actif'),
        ),
    ]
