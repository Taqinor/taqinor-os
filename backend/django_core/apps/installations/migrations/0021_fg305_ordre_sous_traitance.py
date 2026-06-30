# Generated for FG305 — Ordres de travaux émis aux sous-traitants chantier.
# Additif : on AJOUTE une seule table (OrdreSousTraitance). Aucune colonne d'une
# table existante n'est modifiée. Aucune migration destructive.
#
# OrdreSousTraitance référence authentication.Company (multi-tenant),
# installations.SousTraitant (annuaire FG304, PROTECT), installations.Installation
# (chantier optionnel, SET_NULL) et l'utilisateur (created_by, swappable).
# Numérotation OST-YYYYMM-NNNN anti-collision (jamais count()+1), unicité
# (company, reference).
# Noms d'index ≤ 30 caractères (contrainte Django/Postgres) : idx_ost_co_statut,
# idx_ost_co_soustrait.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0020_fg304_sous_traitant'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='OrdreSousTraitance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reference', models.CharField(max_length=50)),
                ('prestation', models.TextField()),
                ('montant', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('montant_realise', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ('date_emission', models.DateField(blank=True, null=True)),
                ('date_echeance', models.DateField(blank=True, null=True)),
                ('statut', models.CharField(choices=[('brouillon', 'Brouillon'), ('emis', 'Émis'), ('en_cours', 'En cours'), ('receptionne', 'Réceptionné'), ('clos', 'Clos')], default='brouillon', max_length=20)),
                ('note', models.TextField(blank=True, null=True)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('date_modification', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='installations_ordres_sous_traitance', to='authentication.company')),
                ('sous_traitant', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='installations_ordres_sous_traitance', to='installations.soustraitant')),
                ('chantier', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installations_ordres_sous_traitance', to='installations.installation')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installations_ordres_sous_traitance_crees', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Ordre de sous-traitance',
                'verbose_name_plural': 'Ordres de sous-traitance',
                'ordering': ['-date_creation'],
                'unique_together': {('company', 'reference')},
            },
        ),
        migrations.AddIndex(
            model_name='ordresoustraitance',
            index=models.Index(fields=['company', 'statut'], name='idx_ost_co_statut'),
        ),
        migrations.AddIndex(
            model_name='ordresoustraitance',
            index=models.Index(fields=['company', 'sous_traitant'], name='idx_ost_co_soustrait'),
        ),
    ]
