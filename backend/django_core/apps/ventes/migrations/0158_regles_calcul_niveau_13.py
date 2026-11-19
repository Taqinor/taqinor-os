# Décision fondateur du 19/11/2026 — « nouveaux rendus seulement », niveau 13
# (REGLES_CYCLES_BATTERIE_1911) : le remplacement de la batterie du flux 25 ans
# de l'option C&I « avec batterie » est lu sur les cycles publiés de la fiche ÷
# les cycles par an de l'étude. Les devis non brouillons GARDENT leur niveau :
# aucune écriture sur eux, ils gardent ce que le client a reçu. Les brouillons
# jamais envoyés au niveau 12 passent à 13 ; tout devis neuf naît en 13.
# Réversible : le retour ramène les 13 à 12.

from django.db import migrations, models


#: YOPSB4 — mise à jour par lots (batch) de clés primaires, comme 0142-0153.
TAILLE_LOT = 500


def _par_lots(Devis, ids, valeur):
    for debut in range(0, len(ids), TAILLE_LOT):
        lot = ids[debut:debut + TAILLE_LOT]
        Devis.objects.filter(pk__in=lot).update(regles_calcul=valeur)


def brouillons_au_niveau_13(apps, schema_editor):
    Devis = apps.get_model('ventes', 'Devis')
    ids = list(Devis.objects
               .filter(statut='brouillon', date_envoi__isnull=True,
                       regles_calcul=12)
               .order_by('pk').values_list('pk', flat=True))
    _par_lots(Devis, ids, 13)


def retour_niveau_12(apps, schema_editor):
    Devis = apps.get_model('ventes', 'Devis')
    ids = list(Devis.objects.filter(regles_calcul=13)
               .order_by('pk').values_list('pk', flat=True))
    _par_lots(Devis, ids, 12)


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0157_ntplt33_devis_fts_null'),
    ]

    operations = [
        migrations.AlterField(
            model_name='devis',
            name='regles_calcul',
            field=models.PositiveSmallIntegerField(default=13),
        ),
        migrations.RunPython(brouillons_au_niveau_13, retour_niveau_12),
    ]
