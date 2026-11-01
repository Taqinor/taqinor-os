# Contre-visite AMOT du 31/10/2026 (C-AMOT-VER-003/006) — « nouveaux rendus
# seulement », niveau 7 : le payback du curseur de stockage, de l'échelle
# batterie et de la carte « avec » de repli suit la définition de ``roi_a``.
# Les devis non brouillons GARDENT leur niveau : aucune écriture sur eux, ils
# gardent les paybacks que le client a reçus. Les brouillons jamais envoyés au
# niveau 6 passent à 7 (aucun client ne les a vus) ; tout devis neuf naît en 7.
# Réversible : le retour arrière ramène les 7 à 6 et rend le défaut 6.

from django.db import migrations, models


#: YOPSB4 — mise à jour par lots (batch) de clés primaires, comme 0142-0145.
TAILLE_LOT = 500


def _par_lots(Devis, ids, valeur):
    for debut in range(0, len(ids), TAILLE_LOT):
        lot = ids[debut:debut + TAILLE_LOT]
        Devis.objects.filter(pk__in=lot).update(regles_calcul=valeur)


def brouillons_au_niveau_7(apps, schema_editor):
    Devis = apps.get_model('ventes', 'Devis')
    ids = list(Devis.objects
               .filter(statut='brouillon', date_envoi__isnull=True,
                       regles_calcul=6)
               .order_by('pk').values_list('pk', flat=True))
    _par_lots(Devis, ids, 7)


def retour_niveau_6(apps, schema_editor):
    Devis = apps.get_model('ventes', 'Devis')
    ids = list(Devis.objects.filter(regles_calcul=7)
               .order_by('pk').values_list('pk', flat=True))
    _par_lots(Devis, ids, 6)


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0145_regles_calcul_niveau_6'),
    ]

    operations = [
        migrations.AlterField(
            model_name='devis',
            name='regles_calcul',
            field=models.PositiveSmallIntegerField(default=7),
        ),
        migrations.RunPython(brouillons_au_niveau_7, retour_niveau_6),
    ]
