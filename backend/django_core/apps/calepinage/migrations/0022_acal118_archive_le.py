# ACAL118 (C-ACAL-099) — l'état ARCHIVÉ porté par le modèle (survit à la
# purge de rétention de la corbeille). Schéma : colonne ``archive_le``
# (nullable : aucune réécriture de table). Données : chaque calepinage qui a
# une entrée de corbeille ACTIVE reçoit ``archive_le = supprime_le`` — par
# LOTS (``iterator(chunk_size=…)``), une ligne mise à jour par entrée, jamais
# un UPDATE global. Réversible : l'inverse des données est un no-op (la
# corbeille garde son journal), puis la colonne est retirée. L'index
# (société, archive_le) est posé CONCURREMMENT par la migration 0023.
from django.db import migrations, models

TAILLE_LOT = 500


def porter_l_archivage(apps, schema_editor):
    ContentType = apps.get_model('contenttypes', 'ContentType')
    ElementSupprime = apps.get_model('trash', 'ElementSupprime')
    Calepinage = apps.get_model('calepinage', 'Calepinage')
    content_type = ContentType.objects.filter(
        app_label='calepinage', model='calepinage').first()
    if content_type is None:
        return
    entrees = (ElementSupprime.objects
               .filter(content_type=content_type, restaure_le__isnull=True)
               .values_list('object_id', 'supprime_le')
               .iterator(chunk_size=TAILLE_LOT))
    for object_id, supprime_le in entrees:
        (Calepinage.objects
         .filter(pk=object_id, archive_le__isnull=True)
         .update(archive_le=supprime_le))


class Migration(migrations.Migration):

    dependencies = [
        ('calepinage', '0021_ciq136_contraintes_site'),
        ('trash', '0001_initial'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='calepinage',
            name='archive_le',
            field=models.DateTimeField(blank=True, null=True,
                                       verbose_name='Archivé le'),
        ),
        migrations.RunPython(porter_l_archivage,
                             migrations.RunPython.noop),
    ]
