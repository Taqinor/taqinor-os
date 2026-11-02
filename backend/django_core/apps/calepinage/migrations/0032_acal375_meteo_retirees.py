# ACAL375 (C-ACAL-VER2-71) — marqueur durable des pièces météo retirées.
#
# Additive. La recopie reporte dans ``meteo_retirees`` les pièces « meteo/ »
# dont l'entrée de corbeille est encore ACTIVE (retirées avant la migration,
# que la purge à J+30 aurait fait revenir). Réversible : RemoveField.
from django.db import migrations, models

TAILLE_LOT = 500


def recopier(apps, schema_editor):
    Element = apps.get_model('trash', 'ElementSupprime')
    Attachment = apps.get_model('records', 'Attachment')
    Calepinage = apps.get_model('calepinage', 'Calepinage')
    CType = apps.get_model('contenttypes', 'ContentType')
    ct_piece = CType.objects.filter(app_label='records',
                                    model='attachment').first()
    ct_cal = CType.objects.filter(app_label='calepinage',
                                  model='calepinage').first()
    if ct_piece is None or ct_cal is None:
        return
    ids = Element.objects.filter(
        content_type=ct_piece, restaure_le__isnull=True,
    ).values_list('object_id', flat=True)
    pieces = Attachment.objects.filter(
        pk__in=list(ids), content_type=ct_cal, file_key__startswith='meteo/')
    par_cal = {}
    for pk, cal_id in pieces.values_list('pk', 'object_id'):
        par_cal.setdefault(cal_id, []).append(pk)
    # YOPSB4 — par lots, comme les recopies 0142-0148 de ventes.
    lignes = sorted(par_cal.items())
    for debut in range(0, len(lignes), TAILLE_LOT):
        batch = lignes[debut:debut + TAILLE_LOT]
        for cal_id, pks in batch:
            Calepinage.objects.filter(pk=cal_id).update(meteo_retirees=sorted(pks))


class Migration(migrations.Migration):

    dependencies = [
        ('calepinage', '0031_acal320_retrait_gabarits_dossier'),
        ('trash', '0001_initial'),
        ('records', '0013_vx210_snooze_trigger_event'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='calepinage',
            name='meteo_retirees',
            field=models.JSONField(blank=True, default=list,
                                   verbose_name='Pièces météo retirées'),
        ),
        migrations.RunPython(recopier, migrations.RunPython.noop),
    ]
