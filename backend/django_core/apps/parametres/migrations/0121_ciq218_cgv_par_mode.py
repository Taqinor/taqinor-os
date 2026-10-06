"""CIQ218 — ``DocumentTemplates.cgv_par_mode`` : conditions générales C&I par
mode (commercial, industriel), texte de la société relu par un juriste.

ADDITIF : une colonne JSON vide par défaut, aucun texte inventé, aucun modèle
existant modifié. Réversible : ``python manage.py migrate parametres 0120``.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0120_ciq211_reglages_ci'),
    ]

    operations = [
        migrations.AddField(
            model_name='documenttemplates',
            name='cgv_par_mode',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
