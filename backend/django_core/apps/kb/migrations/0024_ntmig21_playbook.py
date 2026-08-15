"""NTMIG21 — type d'article « playbook » + structure phases → étapes.

Strictement ADDITIF et RÉVERSIBLE : trois colonnes avec valeur par défaut
(``article`` / liste vide) — aucune ligne existante n'est modifiée, aucun
comportement historique n'est affecté. ``KbArticleVersion`` reçoit la même
colonne de structure pour que le versionnage EXISTANT (jamais un 2ᵉ moteur)
fige aussi les phases d'un playbook.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('kb', '0023_xsav22_portail_deflection'),
    ]

    operations = [
        migrations.AddField(
            model_name='kbarticle',
            name='type_article',
            field=models.CharField(
                choices=[('article', 'Article'),
                         ('playbook', "Playbook d'implémentation")],
                default='article', max_length=10,
                verbose_name="Type d'article"),
        ),
        migrations.AddField(
            model_name='kbarticle',
            name='contenu_structure',
            field=models.JSONField(
                blank=True, default=list,
                verbose_name='Structure (phases → étapes)'),
        ),
        migrations.AddField(
            model_name='kbarticleversion',
            name='contenu_structure',
            field=models.JSONField(
                blank=True, default=list,
                verbose_name='Structure (phases → étapes)'),
        ),
    ]
