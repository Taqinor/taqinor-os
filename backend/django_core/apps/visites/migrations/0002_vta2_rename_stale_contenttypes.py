# VTA2 — préserve tout GenericForeignKey déjà enregistré qui pointe vers une
# VisiteTerrain / un VisiteMedia via django_content_type (pièces jointes
# génériques, LogEntry admin, journaux d'audit), ainsi que les permissions
# Django adossées à ces ContentType.
#
# Renommer l'app_label EN PLACE (même id de ContentType) au lieu de laisser
# Django en créer un nouveau sous 'visites' : tout couple
# (content_type_id, object_id) déjà stocké continue de résoudre exactement le
# même objet. Zéro SQL sur les tables métier (crm_visiteterrain,
# crm_visitemedia) — cette migration ne touche QUE django_content_type, et
# uniquement des lignes déjà existantes (no-op complet sur une base fraîche).
# Réversible (l'inverse repointe sur 'crm').
#
# Même recette qu'ODX15 (apps/frais/migrations/0002_…).
from django.db import migrations

MOVED_MODELS = ['visiteterrain', 'visitemedia']


def _repointer(apps, depuis, vers):
    """Repointe ligne à ligne — jamais un UPDATE de queryset global.

    ``django_content_type`` est unique sur ``(app_label, model)`` : chaque
    itération touche AU PLUS UNE ligne, donc aucun verrou long possible
    (garde-fou YOPSB4 satisfait par construction, pas par dérogation).
    """
    ContentType = apps.get_model('contenttypes', 'ContentType')
    for model in MOVED_MODELS:
        # Une éventuelle ContentType(vers, model) créée trop tôt (commande
        # manage.py lancée entre-temps) doit céder la place : aucune ligne ne
        # peut encore la référencer avant cette migration.
        doublon = ContentType.objects.filter(
            app_label=vers, model=model).first()
        if doublon is not None:
            doublon.delete()
        ancien = ContentType.objects.filter(
            app_label=depuis, model=model).first()
        if ancien is None:
            continue  # base fraîche : rien à repointer.
        ancien.app_label = vers
        ancien.save(update_fields=['app_label'])


def rename_forward(apps, schema_editor):
    _repointer(apps, 'crm', 'visites')


def rename_backward(apps, schema_editor):
    _repointer(apps, 'visites', 'crm')


class Migration(migrations.Migration):

    dependencies = [
        ('visites', '0001_vta2_visites_split'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.RunPython(rename_forward, rename_backward),
    ]
