# Décision fondateur 30/10/2026 (D-ENF-ARRONDI-PDF) — « nouveaux rendus
# seulement », niveau 6 : l'argent affiché par le moteur de devis est arrondi
# moitié vers le haut (``core.money.quantize_mad``) au lieu de l'arrondi
# bancaire de ``round()``. Les devis non brouillons GARDENT leur niveau : aucune
# écriture sur eux, ils gardent l'arrondi que le client a reçu. Les brouillons
# jamais envoyés au niveau 5 passent à 6 (aucun client ne les a vus) ; tout
# devis neuf naît en 6. Réversible : le retour arrière ramène les 6 à 5 et rend
# le défaut 5.

from django.db import migrations, models


#: YOPSB4 — mise à jour par lots (batch) de clés primaires, comme 0142-0144.
TAILLE_LOT = 500


def _par_lots(Devis, ids, valeur):
    for debut in range(0, len(ids), TAILLE_LOT):
        lot = ids[debut:debut + TAILLE_LOT]
        Devis.objects.filter(pk__in=lot).update(regles_calcul=valeur)


def brouillons_au_niveau_6(apps, schema_editor):
    Devis = apps.get_model('ventes', 'Devis')
    ids = list(Devis.objects
               .filter(statut='brouillon', date_envoi__isnull=True,
                       regles_calcul=5)
               .order_by('pk').values_list('pk', flat=True))
    _par_lots(Devis, ids, 6)


def retour_niveau_5(apps, schema_editor):
    Devis = apps.get_model('ventes', 'Devis')
    ids = list(Devis.objects.filter(regles_calcul=6)
               .order_by('pk').values_list('pk', flat=True))
    _par_lots(Devis, ids, 5)


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0144_regles_calcul_niveau_5'),
    ]

    operations = [
        migrations.AlterField(
            model_name='devis',
            name='regles_calcul',
            field=models.PositiveSmallIntegerField(default=6),
        ),
        migrations.RunPython(brouillons_au_niveau_6, retour_niveau_5),
    ]
