# Generated for FG308 — Évaluation de performance des sous-traitants chantier.
# Additif : on AJOUTE une seule table (EvaluationSousTraitant). Aucune colonne
# d'une table existante n'est modifiée. Aucune migration destructive.
# Nom d'index ≤ 30 caractères : idx_eval_co_soustrait.

import django.core.validators
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0023_fg307_attestation_soustraitant'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='EvaluationSousTraitant',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('note_qualite', models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)])),
                ('note_delai', models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)])),
                ('note_securite', models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)])),
                ('commentaire', models.TextField(blank=True, null=True)),
                ('date_evaluation', models.DateField(blank=True, null=True)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('date_modification', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='installations_evaluations_sous_traitant', to='authentication.company')),
                ('sous_traitant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='evaluations', to='installations.soustraitant')),
                ('ordre', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='evaluations', to='installations.ordresoustraitance')),
                ('chantier', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installations_evaluations_sous_traitant', to='installations.installation')),
                ('evalue_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installations_evaluations_sous_traitant_faites', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Évaluation sous-traitant',
                'verbose_name_plural': 'Évaluations sous-traitant',
                'ordering': ['-date_creation'],
            },
        ),
        migrations.AddIndex(
            model_name='evaluationsoustraitant',
            index=models.Index(fields=['company', 'sous_traitant'], name='idx_eval_co_soustrait'),
        ),
    ]
