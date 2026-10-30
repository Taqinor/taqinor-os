# Décision fondateur 30/10/2026 (D-CI-SENSIB-ENVOYES) — « nouveaux rendus
# seulement », niveau 5 (ERR-CEC6-RETOUR-AVEC-BATTERIE-PERDU : retour de
# l'option « avec batterie » d'un devis C&I non accepté ;
# ERR-AMOT59-CURSEUR-STOCKAGE-PRIX : curseur de stockage ancré sur le TTC du
# devis). Le niveau 4 (0143) est en production : des devis ont pu être envoyés
# au niveau 4. Les devis non brouillons GARDENT leur niveau : aucune écriture
# sur eux. Les brouillons jamais envoyés au niveau 4 passent à 5 (aucun client
# ne les a vus) ; tout devis neuf naît en 5. Réversible : le retour arrière
# ramène les 5 à 4 et rend le défaut 4.

from django.db import migrations, models


#: YOPSB4 — mise à jour par lots (batch) de clés primaires, comme 0142/0143.
TAILLE_LOT = 500


def _par_lots(Devis, ids, valeur):
    for debut in range(0, len(ids), TAILLE_LOT):
        lot = ids[debut:debut + TAILLE_LOT]
        Devis.objects.filter(pk__in=lot).update(regles_calcul=valeur)


def brouillons_au_niveau_5(apps, schema_editor):
    Devis = apps.get_model('ventes', 'Devis')
    ids = list(Devis.objects
               .filter(statut='brouillon', date_envoi__isnull=True,
                       regles_calcul=4)
               .order_by('pk').values_list('pk', flat=True))
    _par_lots(Devis, ids, 5)


def retour_niveau_4(apps, schema_editor):
    Devis = apps.get_model('ventes', 'Devis')
    ids = list(Devis.objects.filter(regles_calcul=5)
               .order_by('pk').values_list('pk', flat=True))
    _par_lots(Devis, ids, 4)


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0143_regles_calcul_niveau_3010'),
    ]

    operations = [
        migrations.AlterField(
            model_name='devis',
            name='regles_calcul',
            field=models.PositiveSmallIntegerField(default=5),
        ),
        migrations.RunPython(brouillons_au_niveau_5, retour_niveau_4),
    ]
