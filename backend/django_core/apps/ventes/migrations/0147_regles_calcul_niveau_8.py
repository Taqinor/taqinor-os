# Contre-visite AGNR du 01/11/2026 (C-AGNR-VER-007, AGNR54) — « nouveaux
# rendus seulement », niveau 8 : la consommation de tous les lecteurs publics
# d'un devis est résolue par ``etude_horaire.profil_conso_du_devis`` (factures
# écran, kWh déclaré CAD166, barème société), la même série que l'étude.
# Les devis non brouillons GARDENT leur niveau : aucune écriture sur eux, ils
# gardent la page que le client a reçue. Les brouillons jamais envoyés au
# niveau 7 passent à 8 (aucun client ne les a vus) ; tout devis neuf naît en 8.
# Réversible : le retour arrière ramène les 8 à 7 et rend le défaut 7.

from django.db import migrations, models


#: YOPSB4 — mise à jour par lots (batch) de clés primaires, comme 0142-0146.
TAILLE_LOT = 500


def _par_lots(Devis, ids, valeur):
    for debut in range(0, len(ids), TAILLE_LOT):
        lot = ids[debut:debut + TAILLE_LOT]
        Devis.objects.filter(pk__in=lot).update(regles_calcul=valeur)


def brouillons_au_niveau_8(apps, schema_editor):
    Devis = apps.get_model('ventes', 'Devis')
    ids = list(Devis.objects
               .filter(statut='brouillon', date_envoi__isnull=True,
                       regles_calcul=7)
               .order_by('pk').values_list('pk', flat=True))
    _par_lots(Devis, ids, 8)


def retour_niveau_7(apps, schema_editor):
    Devis = apps.get_model('ventes', 'Devis')
    ids = list(Devis.objects.filter(regles_calcul=8)
               .order_by('pk').values_list('pk', flat=True))
    _par_lots(Devis, ids, 7)


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0146_regles_calcul_niveau_7'),
    ]

    operations = [
        migrations.AlterField(
            model_name='devis',
            name='regles_calcul',
            field=models.PositiveSmallIntegerField(default=8),
        ),
        migrations.RunPython(brouillons_au_niveau_8, retour_niveau_7),
    ]
