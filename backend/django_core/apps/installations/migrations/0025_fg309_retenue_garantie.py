# Generated for FG309 — Retenue de garantie sur sous-traitant (BTP marocain).
# Additif : on AJOUTE une seule table (RetenueGarantieSousTraitant). Aucune
# colonne d'une table existante n'est modifiée. Aucune migration destructive.
# Noms d'index ≤ 30 caractères : idx_rg_co_levee, idx_rg_co_ordre.

import django.core.validators
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0024_fg308_evaluation_soustraitant'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='RetenueGarantieSousTraitant',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('pourcentage', models.DecimalField(decimal_places=2, default=Decimal('10'), max_digits=5, validators=[django.core.validators.MinValueValidator(Decimal('0')), django.core.validators.MaxValueValidator(Decimal('100'))])),
                ('levee', models.BooleanField(default=False)),
                ('date_constitution', models.DateField(blank=True, null=True)),
                ('date_levee', models.DateField(blank=True, null=True)),
                ('note', models.TextField(blank=True, null=True)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('date_modification', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='installations_retenues_garantie', to='authentication.company')),
                ('ordre', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='retenues_garantie', to='installations.ordresoustraitance')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installations_retenues_garantie_creees', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Retenue de garantie sous-traitant',
                'verbose_name_plural': 'Retenues de garantie sous-traitant',
                'ordering': ['-date_creation'],
            },
        ),
        migrations.AddIndex(
            model_name='retenuegarantiesoustraitant',
            index=models.Index(fields=['company', 'levee'], name='idx_rg_co_levee'),
        ),
        migrations.AddIndex(
            model_name='retenuegarantiesoustraitant',
            index=models.Index(fields=['company', 'ordre'], name='idx_rg_co_ordre'),
        ),
    ]
