"""CHT23 — Gates : exigences photo/checklist configurables par étape.

Ajoute ``StageModele.photos_min`` (défaut 0) et ``checklist_pct_min`` (défaut
100). ADDITIF STRICT : à leurs valeurs par défaut, les gates
``exige_checklist``/``exige_photos`` restent inconditionnellement le
comportement historique (« tous faits ») — ``photos_min`` > 0 AJOUTE une
contrainte de comptage réel de photos, ``checklist_pct_min`` < 100 assouplit
en « ≥ pct % faits ». Aucune donnée existante n'est modifiée.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0104_aud321_jalonprojet_unique_phase'),
    ]

    operations = [
        migrations.AddField(
            model_name='stagemodele',
            name='photos_min',
            field=models.PositiveSmallIntegerField(
                default=0, verbose_name='Nombre de photos minimum'),
        ),
        migrations.AddField(
            model_name='stagemodele',
            name='checklist_pct_min',
            field=models.PositiveSmallIntegerField(
                default=100, verbose_name='% de checklist minimum'),
        ),
    ]
