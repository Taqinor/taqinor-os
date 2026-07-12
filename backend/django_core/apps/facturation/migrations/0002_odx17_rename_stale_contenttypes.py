# ODX17 — préserve les GenericForeignKey existants (ex. ged.DocumentLien) qui
# pointent vers une Facture/un Paiement/un Avoir via django_content_type.
#
# Renommer l'app_label EN PLACE (même id de ContentType) au lieu de laisser
# Django en créer un nouveau sous 'facturation' : tout GenericForeignKey déjà
# enregistré (content_type_id + object_id) continue de résoudre exactement le
# même objet, sans aucune migration de données sur les lignes elles-mêmes.
# Zéro SQL sur les tables métier (ventes_facture, ventes_paiement, …) — cette
# migration ne touche QUE django_content_type, et seulement les lignes qui
# existent déjà (no-op sur une base fraîche sans ContentType 'ventes.*'
# préexistant pour ces modèles).
from django.db import migrations

MOVED_MODELS = [
    'facture', 'lignefacture', 'paiement', 'avoir', 'ligneavoir',
    'followuplevel', 'relancelog',
]


def rename_forward(apps, schema_editor):
    ContentType = apps.get_model('contenttypes', 'ContentType')
    for model in MOVED_MODELS:
        # Une éventuelle ContentType('facturation', model) créée trop tôt
        # (ex. commande manage.py lancée entre-temps) doit céder la place —
        # on la supprime d'abord si elle est vide (aucune ligne référençant
        # un objet 'facturation' ne peut exister avant cette migration).
        ContentType.objects.filter(
            app_label='facturation', model=model).delete()
        ContentType.objects.filter(
            app_label='ventes', model=model
        ).update(app_label='facturation')


def rename_backward(apps, schema_editor):
    ContentType = apps.get_model('contenttypes', 'ContentType')
    for model in MOVED_MODELS:
        ContentType.objects.filter(
            app_label='facturation', model=model
        ).update(app_label='ventes')


class Migration(migrations.Migration):

    dependencies = [
        ('facturation', '0001_odx17_facturation_split'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.RunPython(rename_forward, rename_backward),
    ]
