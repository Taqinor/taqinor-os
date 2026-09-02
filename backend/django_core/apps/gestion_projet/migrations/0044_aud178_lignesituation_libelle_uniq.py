# AUD178 — un lot n'apparaît qu'UNE fois par situation de travaux.
#
# ``services.ajouter_ligne_situation`` promettait « ajoute (ou remplace) » mais
# créait inconditionnellement une nouvelle ``LigneSituation`` : rappeler
# ``ajouter-ligne`` avec le même libellé pour CORRIGER un avancement créait un
# doublon que ``valider_situation`` facturait deux fois.
#
# La contrainte est posée sur des données potentiellement peuplées : l'étape de
# préparation ne SUPPRIME rien (aucune perte de données, migration revertable)
# — elle RENOMME les doublons ANTÉRIEURS en « <libellé> (doublon n) », laissant
# la ligne la PLUS RÉCENTE (la correction) porter le libellé canonique. C'est
# exactement la sémantique que le correctif applique désormais en ligne :
# ``_situation_precedente_montant_cumule`` retrouve la valeur corrigée, plus
# l'erreur d'origine.
from django.db import migrations, models


def _renommer_doublons(apps, schema_editor):
    LigneSituation = apps.get_model('gestion_projet', 'LigneSituation')
    vus = {}
    for ligne in LigneSituation.objects.order_by('situation_id', '-id').only(
            'id', 'situation_id', 'libelle').iterator():
        cle = (ligne.situation_id, ligne.libelle)
        rang = vus.get(cle, 0)
        vus[cle] = rang + 1
        if rang == 0:
            # La plus récente garde le libellé canonique.
            continue
        nouveau = f'{ligne.libelle} (doublon {rang})'[:200]
        LigneSituation.objects.filter(pk=ligne.pk).update(libelle=nouveau)


def _annuler_renommage(apps, schema_editor):
    """Revert : rien à défaire (les libellés renommés restent lisibles)."""
    return None


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_projet', '0043_aud309_versiondocument_minio'),
    ]

    operations = [
        migrations.RunPython(_renommer_doublons, _annuler_renommage),
        migrations.AddConstraint(
            model_name='lignesituation',
            constraint=models.UniqueConstraint(
                fields=('situation', 'libelle'),
                name='gp_lignesit_situation_libelle_uniq'),
        ),
    ]
