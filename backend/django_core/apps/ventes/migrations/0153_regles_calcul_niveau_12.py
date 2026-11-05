# AMOT118 (C-AMOT-VER4-010, 04/11/2026) — « nouveaux rendus seulement », niveau 12
# (REGLES_ECARTS_0411) : contrat unique des correctifs de chiffres AMOT120-AMOT123,
# AMOT126. Les devis non brouillons GARDENT leur niveau : aucune écriture sur eux,
# ils gardent ce que le client a reçu. Les brouillons jamais envoyés au niveau 11
# passent à 12 ; tout devis neuf naît en 12. Réversible : le retour ramène les 12 à 11.

from django.db import migrations, models


#: YOPSB4 — mise à jour par lots (batch) de clés primaires, comme 0142-0151.
TAILLE_LOT = 500


def _par_lots(Devis, ids, valeur):
    for debut in range(0, len(ids), TAILLE_LOT):
        lot = ids[debut:debut + TAILLE_LOT]
        Devis.objects.filter(pk__in=lot).update(regles_calcul=valeur)


def brouillons_au_niveau_12(apps, schema_editor):
    Devis = apps.get_model('ventes', 'Devis')
    ids = list(Devis.objects
               .filter(statut='brouillon', date_envoi__isnull=True,
                       regles_calcul=11)
               .order_by('pk').values_list('pk', flat=True))
    _par_lots(Devis, ids, 12)


def retour_niveau_11(apps, schema_editor):
    Devis = apps.get_model('ventes', 'Devis')
    ids = list(Devis.objects.filter(regles_calcul=12)
               .order_by('pk').values_list('pk', flat=True))
    _par_lots(Devis, ids, 11)


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0152_retenuesubie_annulee'),
    ]

    operations = [
        migrations.AlterField(
            model_name='devis',
            name='regles_calcul',
            field=models.PositiveSmallIntegerField(default=12),
        ),
        migrations.RunPython(brouillons_au_niveau_12, retour_niveau_11),
    ]
