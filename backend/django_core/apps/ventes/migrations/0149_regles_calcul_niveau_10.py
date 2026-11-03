# ADVS5/ADVS6 (D-ADVS-3, 02/11/2026) — « nouveaux rendus seulement », niveau 10 :
# une seule règle range chaque ligne dans ses options (PDF, page, argent du noyau).
# Les devis non brouillons GARDENT leur niveau : aucune écriture sur eux, ils
# gardent le total d'option et l'acompte que le client a reçus (câble batterie,
# batterie au nom sans « batterie »). Les brouillons jamais envoyés au niveau 9
# passent à 10 (aucun client ne les a vus) ; tout devis neuf naît en 10.
# Réversible : le retour arrière ramène les 10 à 9 et rend le défaut 9.

from django.db import migrations, models


#: YOPSB4 — mise à jour par lots (batch) de clés primaires, comme 0142-0148.
TAILLE_LOT = 500


def _par_lots(Devis, ids, valeur):
    for debut in range(0, len(ids), TAILLE_LOT):
        lot = ids[debut:debut + TAILLE_LOT]
        Devis.objects.filter(pk__in=lot).update(regles_calcul=valeur)


def brouillons_au_niveau_10(apps, schema_editor):
    Devis = apps.get_model('ventes', 'Devis')
    ids = list(Devis.objects
               .filter(statut='brouillon', date_envoi__isnull=True,
                       regles_calcul=9)
               .order_by('pk').values_list('pk', flat=True))
    _par_lots(Devis, ids, 10)


def retour_niveau_9(apps, schema_editor):
    Devis = apps.get_model('ventes', 'Devis')
    ids = list(Devis.objects.filter(regles_calcul=10)
               .order_by('pk').values_list('pk', flat=True))
    _par_lots(Devis, ids, 9)


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0148_regles_calcul_niveau_9'),
    ]

    operations = [
        migrations.AlterField(
            model_name='devis',
            name='regles_calcul',
            field=models.PositiveSmallIntegerField(default=10),
        ),
        migrations.RunPython(brouillons_au_niveau_10, retour_niveau_9),
    ]
