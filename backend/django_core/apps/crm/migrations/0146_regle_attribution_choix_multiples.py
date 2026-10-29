"""Règles d'attribution à choix MULTIPLES (fondateur, 28/10/2026).

Une règle peut désormais viser plusieurs types de client et plusieurs
sources : ``type_installation`` / ``source`` (texte, une valeur) deviennent
``types_installation`` / ``sources`` (listes JSON, vide = tous).

Données : une valeur non vide devient une liste d'un élément ; les colonnes
texte restent (obsolètes) jusqu'à une migration de retrait revue. Réversible :
au retour, le PREMIER élément de chaque liste reprend la colonne texte
(``migrate crm 0145``).
"""
from django.db import migrations, models


def vers_listes(apps, schema_editor):
    RegleAttribution = apps.get_model('crm', 'RegleAttribution')
    for regle in RegleAttribution.objects.all().iterator():
        regle.types_installation = (
            [regle.type_installation] if regle.type_installation else [])
        regle.sources = [regle.source] if regle.source else []
        regle.save(update_fields=['types_installation', 'sources'])


def vers_textes(apps, schema_editor):
    RegleAttribution = apps.get_model('crm', 'RegleAttribution')
    for regle in RegleAttribution.objects.all().iterator():
        types = regle.types_installation or []
        sources = regle.sources or []
        regle.type_installation = str(types[0])[:20] if types else ''
        regle.source = str(sources[0])[:20] if sources else ''
        regle.save(update_fields=['type_installation', 'source'])


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0145_attribution_responsable'),
    ]

    operations = [
        migrations.AddField(
            model_name='regleattribution',
            name='types_installation',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='regleattribution',
            name='sources',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(vers_listes, vers_textes),
        # Les colonnes texte restent (obsolètes, non servies) : pas de
        # RemoveField dans une migration neuve (garde YOPSB4) — expand/contract.
    ]
