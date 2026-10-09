# Décision fondateur 08/10/2026 — « nouveaux rendus seulement » : les devis
# déjà envoyés gardent les règles de calcul d'origine (1) ; les autres (et
# tout devis créé ensuite) suivent les règles corrigées (2). AddField +
# RunPython réversible (le retour arrière supprime simplement la colonne).

from django.db import migrations, models


#: YOPSB4 — mise à jour par lots (batch) de clés primaires (jamais un UPDATE global
#: qui verrouillerait longtemps la table des devis).
TAILLE_LOT = 500


def figer_devis_envoyes(apps, schema_editor):
    Devis = apps.get_model('ventes', 'Devis')
    ids = list(Devis.objects
               .exclude(statut='brouillon', date_envoi__isnull=True)
               .order_by('pk').values_list('pk', flat=True))
    for debut in range(0, len(ids), TAILLE_LOT):
        lot = ids[debut:debut + TAILLE_LOT]
        Devis.objects.filter(pk__in=lot).update(regles_calcul=1)


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0135_merge_adev33_atot12'),
    ]

    operations = [
        migrations.AddField(
            model_name='devis',
            name='regles_calcul',
            field=models.PositiveSmallIntegerField(default=2),
        ),
        migrations.RunPython(figer_devis_envoyes, migrations.RunPython.noop),
    ]
