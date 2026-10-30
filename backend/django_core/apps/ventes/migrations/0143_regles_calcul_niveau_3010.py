# Décision fondateur 30/10/2026 (D-CI-SENSIB-ENVOYES) — « nouveaux rendus
# seulement », niveau 4 (ERR-CI-SENSIBILITE-P90-INVERSEE : scénario production
# des sensibilités C&I par le moteur du central). Les devis non brouillons
# GARDENT leur niveau : aucune écriture sur eux, leur PDF régénéré montre le
# tableau que le client a reçu. Les brouillons au niveau 3 passent à 4 (aucun
# client ne les a vus) ; tout devis neuf naît en 4. Réversible : le retour
# arrière ramène les 4 à 3 et rend le défaut 3.

from django.db import migrations, models


#: YOPSB4 — mise à jour par lots (batch) de clés primaires, comme 0142.
TAILLE_LOT = 500


def _par_lots(Devis, ids, valeur):
    for debut in range(0, len(ids), TAILLE_LOT):
        lot = ids[debut:debut + TAILLE_LOT]
        Devis.objects.filter(pk__in=lot).update(regles_calcul=valeur)


def brouillons_au_niveau_4(apps, schema_editor):
    Devis = apps.get_model('ventes', 'Devis')
    ids = list(Devis.objects
               .filter(statut='brouillon', date_envoi__isnull=True,
                       regles_calcul=3)
               .order_by('pk').values_list('pk', flat=True))
    _par_lots(Devis, ids, 4)


def retour_niveau_3(apps, schema_editor):
    Devis = apps.get_model('ventes', 'Devis')
    ids = list(Devis.objects.filter(regles_calcul=4)
               .order_by('pk').values_list('pk', flat=True))
    _par_lots(Devis, ids, 3)


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0142_regles_calcul_niveau_2710'),
    ]

    operations = [
        migrations.AlterField(
            model_name='devis',
            name='regles_calcul',
            field=models.PositiveSmallIntegerField(default=4),
        ),
        migrations.RunPython(brouillons_au_niveau_4, retour_niveau_3),
    ]
