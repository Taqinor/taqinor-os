# Contre-visite AMOT du 01/11/2026 (C-AMOT-VER-040/030, AMOT116, AMOT115) —
# « nouveaux rendus seulement », niveau 9 : un devis C&I à consommation connue
# nomme le manque réel au lieu de « vos 12 dernières factures » ; en base
# « deux », chaque carte d'option imprime l'économie TTC à côté de la HT.
# Les devis non brouillons GARDENT leur niveau : aucune écriture sur eux, ils
# gardent la phrase et les cartes que le client a reçues. Les brouillons jamais
# envoyés au niveau 8 passent à 9 (aucun client ne les a vus) ; tout devis neuf
# naît en 9. Réversible : le retour arrière ramène les 9 à 8 et rend le défaut 8.

from django.db import migrations, models


#: YOPSB4 — mise à jour par lots (batch) de clés primaires, comme 0142-0147.
TAILLE_LOT = 500


def _par_lots(Devis, ids, valeur):
    for debut in range(0, len(ids), TAILLE_LOT):
        lot = ids[debut:debut + TAILLE_LOT]
        Devis.objects.filter(pk__in=lot).update(regles_calcul=valeur)


def brouillons_au_niveau_9(apps, schema_editor):
    Devis = apps.get_model('ventes', 'Devis')
    ids = list(Devis.objects
               .filter(statut='brouillon', date_envoi__isnull=True,
                       regles_calcul=8)
               .order_by('pk').values_list('pk', flat=True))
    _par_lots(Devis, ids, 9)


def retour_niveau_8(apps, schema_editor):
    Devis = apps.get_model('ventes', 'Devis')
    ids = list(Devis.objects.filter(regles_calcul=9)
               .order_by('pk').values_list('pk', flat=True))
    _par_lots(Devis, ids, 8)


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0147_regles_calcul_niveau_8'),
    ]

    operations = [
        migrations.AlterField(
            model_name='devis',
            name='regles_calcul',
            field=models.PositiveSmallIntegerField(default=9),
        ),
        migrations.RunPython(brouillons_au_niveau_9, retour_niveau_8),
    ]
