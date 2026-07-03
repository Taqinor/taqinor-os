# Generated for XRH4 — Checklist d'intégration (onboarding) du nouvel embauché.
#
# Entièrement additive : trois nouveaux modèles (``ModeleIntegration``,
# ``ElementIntegration``, ``ElementIntegrationEmploye``) + index nommés.
# Réversible.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0013_customuser_poste_ref'),
        ('rh', '0040_demi_journee_justificatif'),
    ]

    operations = [
        migrations.CreateModel(
            name='ModeleIntegration',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom', models.CharField(max_length=160, verbose_name='Nom')),
                ('actif', models.BooleanField(default=True, verbose_name='Actif')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rh_modeles_integration', to='authentication.company', verbose_name='Société')),
                ('departement', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='modeles_integration', to='rh.departement', verbose_name='Département (optionnel)')),
                ('poste_ref', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='modeles_integration', to='rh.poste', verbose_name='Poste (optionnel)')),
            ],
            options={
                'verbose_name': "Modèle d'intégration",
                'verbose_name_plural': "Modèles d'intégration",
                'ordering': ['nom'],
            },
        ),
        migrations.CreateModel(
            name='ElementIntegration',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('libelle', models.CharField(max_length=160, verbose_name='Libellé')),
                ('ordre', models.PositiveIntegerField(default=0, verbose_name='Ordre')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rh_elements_integration', to='authentication.company', verbose_name='Société')),
                ('modele', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='elements', to='rh.modeleintegration', verbose_name="Modèle d'intégration")),
            ],
            options={
                'verbose_name': "Élément d'intégration (gabarit)",
                'verbose_name_plural': "Éléments d'intégration (gabarit)",
                'ordering': ['ordre', 'libelle'],
            },
        ),
        migrations.CreateModel(
            name='ElementIntegrationEmploye',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('libelle', models.CharField(max_length=160, verbose_name='Libellé')),
                ('ordre', models.PositiveIntegerField(default=0, verbose_name='Ordre')),
                ('fait', models.BooleanField(default=False, verbose_name='Fait')),
                ('date', models.DateTimeField(blank=True, null=True, verbose_name='Date de réalisation')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rh_elements_integration_employe', to='authentication.company', verbose_name='Société')),
                ('employe', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='elements_integration', to='rh.dossieremploye', verbose_name='Employé')),
                ('fait_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='rh_elements_integration_coches', to=settings.AUTH_USER_MODEL, verbose_name='Fait par')),
            ],
            options={
                'verbose_name': "Élément d'intégration (employé)",
                'verbose_name_plural': "Éléments d'intégration (employé)",
                'ordering': ['ordre', 'libelle'],
            },
        ),
        migrations.AddIndex(
            model_name='elementintegration',
            index=models.Index(fields=['company', 'modele'], name='rh_el_int_comp_mod_idx'),
        ),
        migrations.AddIndex(
            model_name='elementintegrationemploye',
            index=models.Index(fields=['company', 'employe'], name='rh_el_int_emp_comp_idx'),
        ),
    ]
