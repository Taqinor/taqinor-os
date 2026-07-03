# Generated for XRH8 — Horaires de travail par gabarit (44 h, Ramadan,
# saisonnier).
#
# Entièrement additive : nouveau modèle ``HoraireTravail`` + un FK nullable
# ``DossierEmploye.horaire`` + un index nommé. Réversible.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rh', '0043_dossier_activity'),
    ]

    operations = [
        migrations.CreateModel(
            name='HoraireTravail',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom', models.CharField(max_length=120, verbose_name='Nom')),
                ('heures_semaine', models.DecimalField(decimal_places=2, default=44, max_digits=5, verbose_name='Heures / semaine')),
                ('heures_jour_defaut', models.DecimalField(decimal_places=2, default=8, max_digits=5, verbose_name='Heures / jour (défaut)')),
                ('type_horaire', models.CharField(choices=[('standard_44h', 'Standard 44h'), ('ramadan', 'Ramadan'), ('saisonnier', 'Saisonnier'), ('temps_partiel', 'Temps partiel')], default='standard_44h', max_length=15, verbose_name="Type d'horaire")),
                ('date_debut', models.DateField(blank=True, null=True, verbose_name='Début de validité (vide = permanent)')),
                ('date_fin', models.DateField(blank=True, null=True, verbose_name='Fin de validité (vide = permanent)')),
                ('actif', models.BooleanField(default=True, verbose_name='Actif')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rh_horaires_travail', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Horaire de travail',
                'verbose_name_plural': 'Horaires de travail',
                'ordering': ['nom'],
            },
        ),
        migrations.AddField(
            model_name='dossieremploye',
            name='horaire',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='employes', to='rh.horairetravail', verbose_name='Horaire de travail'),
        ),
        migrations.AddIndex(
            model_name='horairetravail',
            index=models.Index(fields=['company', 'date_debut', 'date_fin'], name='rh_horaire_comp_periode_idx'),
        ),
    ]
