# ADVS3 (D-ADVS-4, 03/11/2026) — « nouveaux rendus seulement », niveau 11 : un TTC à
# moins d'1 MAD sous une centaine y remonte au lieu de perdre 100 MAD. Les devis non
# brouillons GARDENT leur niveau : aucune écriture sur eux, ils gardent le total que
# le client a reçu. Les brouillons jamais envoyés au niveau 10 passent à 11 ; tout
# devis neuf naît en 11. Réversible : le retour arrière ramène les 11 à 10.

from django.db import migrations, models


#: YOPSB4 — mise à jour par lots (batch) de clés primaires, comme 0142-0149.
TAILLE_LOT = 500


def _par_lots(Devis, ids, valeur):
    for debut in range(0, len(ids), TAILLE_LOT):
        lot = ids[debut:debut + TAILLE_LOT]
        Devis.objects.filter(pk__in=lot).update(regles_calcul=valeur)


def brouillons_au_niveau_11(apps, schema_editor):
    Devis = apps.get_model('ventes', 'Devis')
    ids = list(Devis.objects
               .filter(statut='brouillon', date_envoi__isnull=True,
                       regles_calcul=10)
               .order_by('pk').values_list('pk', flat=True))
    _par_lots(Devis, ids, 11)


def retour_niveau_10(apps, schema_editor):
    Devis = apps.get_model('ventes', 'Devis')
    ids = list(Devis.objects.filter(regles_calcul=11)
               .order_by('pk').values_list('pk', flat=True))
    _par_lots(Devis, ids, 10)


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0150_devis_signature_archivee'),
    ]

    operations = [
        migrations.AlterField(
            model_name='devis',
            name='regles_calcul',
            field=models.PositiveSmallIntegerField(default=11),
        ),
        migrations.RunPython(brouillons_au_niveau_11, retour_niveau_10),
    ]
