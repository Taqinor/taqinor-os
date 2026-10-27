# Décision fondateur 27/10/2026 (D-RES-2710-1/2) — « nouveaux rendus
# seulement », niveau 3. Les devis non brouillons (envoyés après le 08/10)
# GARDENT 2 : aucune écriture sur eux, le client relit ce qu'il a reçu. Les
# brouillons au niveau 2 passent à 3 — même traitement que 0138, qui laissait
# les brouillons au niveau le plus récent : aucun client ne les a vus. Tout
# devis neuf naît en 3 (nouveau défaut). Réversible : le retour arrière ramène
# les 3 à 2 et rend le défaut 2.

from django.db import migrations, models


#: YOPSB4 — mise à jour par lots de clés primaires (jamais un UPDATE global).
TAILLE_LOT = 500


def _par_lots(Devis, ids, valeur):
    for debut in range(0, len(ids), TAILLE_LOT):
        lot = ids[debut:debut + TAILLE_LOT]
        Devis.objects.filter(pk__in=lot).update(regles_calcul=valeur)


def brouillons_au_niveau_3(apps, schema_editor):
    Devis = apps.get_model('ventes', 'Devis')
    ids = list(Devis.objects
               .filter(statut='brouillon', date_envoi__isnull=True,
                       regles_calcul=2)
               .order_by('pk').values_list('pk', flat=True))
    _par_lots(Devis, ids, 3)


def retour_niveau_2(apps, schema_editor):
    Devis = apps.get_model('ventes', 'Devis')
    ids = list(Devis.objects.filter(regles_calcul=3)
               .order_by('pk').values_list('pk', flat=True))
    _par_lots(Devis, ids, 2)


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0141_vnt103_retrait_acompte_devis'),
    ]

    operations = [
        migrations.AlterField(
            model_name='devis',
            name='regles_calcul',
            field=models.PositiveSmallIntegerField(default=3),
        ),
        migrations.RunPython(brouillons_au_niveau_3, retour_niveau_2),
    ]
