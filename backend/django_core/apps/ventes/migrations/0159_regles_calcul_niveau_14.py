# Décision fondateur du 19/11/2026 (D-SENS-1, « Yes, fix it ») — « nouveaux
# rendus seulement », niveau 14 (REGLES_SENSIBILITES_1911) : le tableau des
# sensibilités C&I imprime le retour de chaque scénario au dixième et l'option
# « avec batterie » sert ses propres sensibilités. Les devis non brouillons
# GARDENT leur niveau : aucune écriture sur eux, ils gardent le tableau que le
# client a reçu. Les brouillons jamais envoyés au niveau 13 passent à 14 ; tout
# devis neuf naît en 14. Réversible : le retour ramène les 14 à 13.

from django.db import migrations, models


#: YOPSB4 — mise à jour par lots (batch) de clés primaires, comme 0142-0158.
TAILLE_LOT = 500


def _par_lots(Devis, ids, valeur):
    for debut in range(0, len(ids), TAILLE_LOT):
        lot = ids[debut:debut + TAILLE_LOT]
        Devis.objects.filter(pk__in=lot).update(regles_calcul=valeur)


def brouillons_au_niveau_14(apps, schema_editor):
    Devis = apps.get_model('ventes', 'Devis')
    ids = list(Devis.objects
               .filter(statut='brouillon', date_envoi__isnull=True,
                       regles_calcul=13)
               .order_by('pk').values_list('pk', flat=True))
    _par_lots(Devis, ids, 14)


def retour_niveau_13(apps, schema_editor):
    Devis = apps.get_model('ventes', 'Devis')
    ids = list(Devis.objects.filter(regles_calcul=14)
               .order_by('pk').values_list('pk', flat=True))
    _par_lots(Devis, ids, 13)


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0158_regles_calcul_niveau_13'),
    ]

    operations = [
        migrations.AlterField(
            model_name='devis',
            name='regles_calcul',
            field=models.PositiveSmallIntegerField(default=14),
        ),
        migrations.RunPython(brouillons_au_niveau_14, retour_niveau_13),
    ]
