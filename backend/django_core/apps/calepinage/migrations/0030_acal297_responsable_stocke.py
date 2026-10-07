# ACAL297 (C-ACAL-014) — migration de DONNÉES : le responsable d'un
# calepinage est STOCKÉ. Chaque calepinage sans responsable et rattaché à un
# lead reçoit le propriétaire de ce lead (MÊME société) — exactement la valeur
# que le repli de lecture affichait jusqu'ici : rien ne change à l'écran,
# mais le filtre ``?responsable=`` et la vue restreinte lisent enfin la même
# colonne. Lu par ``apps.get_model`` (jamais ``apps.crm.models``), lot par
# lot, une ligne mise à jour par calepinage. Inverse : no-op (la colonne
# remplie reste une valeur juste).
from django.db import migrations

TAILLE_LOT = 500


def stocker_les_responsables(apps, schema_editor):
    Calepinage = apps.get_model('calepinage', 'Calepinage')
    Lead = apps.get_model('crm', 'Lead')
    lignes = (Calepinage.objects
              .filter(responsable__isnull=True, lead_id__isnull=False)
              .order_by('pk')
              .values_list('pk', 'company_id', 'lead_id')
              .iterator(chunk_size=TAILLE_LOT))
    for pk, company_id, lead_id in lignes:
        proprietaire = (Lead.objects
                        .filter(pk=lead_id, company_id=company_id)
                        .values_list('owner_id', flat=True).first())
        if proprietaire:
            (Calepinage.objects.filter(pk=pk, responsable__isnull=True)
             .update(responsable_id=proprietaire))


class Migration(migrations.Migration):

    dependencies = [
        ('calepinage', '0029_acal294_custom_data'),
        ('crm', '0128_ciq517_playbook_8221_condition'),
    ]

    operations = [
        migrations.RunPython(stocker_les_responsables,
                             migrations.RunPython.noop),
    ]
