"""AUD135 — un paiement appartient à AU PLUS UNE remise d'encaissement.

L'unicité était déclarée ``unique_together [('remise', 'paiement')]``, donc PAR
REMISE : rien n'empêchait le même ``Paiement`` d'apparaître dans N remises, et
``RemiseEncaissement.montant_lignes`` le comptait dans CHACUNE. Le même chèque
de 15 000 déclaré dans deux bordereaux faisait apparaître 15 000 de trop au
rapprochement de caisse.

Migration ADDITIVE et RÉVERSIBLE : on remplace la contrainte de paire par une
contrainte d'unicité sur ``paiement`` seul (elle implique l'ancienne). Les
éventuels doublons EXISTANTS sont dédupliqués d'abord — on garde la ligne de la
remise la PLUS ANCIENNE (première déclaration), jamais une suppression de
``Paiement``.
"""
from django.db import migrations, models


def _dedupliquer_lignes(apps, schema_editor):
    """Ne garde qu'UNE ligne par paiement : celle de la remise la plus ancienne.

    Sans ce passage, l'ajout de la contrainte échouerait sur une base portant
    déjà le doublon que la tâche décrit. Aucun ``Paiement`` n'est touché.
    """
    Ligne = apps.get_model('ventes', 'LigneRemiseEncaissement')
    vus = set()
    a_supprimer = []
    # Ordre = remise la plus ancienne d'abord (id croissant), puis ligne.
    for ligne_id, paiement_id in Ligne.objects.order_by(
            'remise_id', 'id').values_list('id', 'paiement_id'):
        if paiement_id in vus:
            a_supprimer.append(ligne_id)
        else:
            vus.add(paiement_id)
    if a_supprimer:
        Ligne.objects.filter(id__in=a_supprimer).delete()


def _noop(apps, schema_editor):
    """Retour arrière : la déduplication n'est pas rejouable (rien à refaire)."""


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0111_aud107_notedebit_remise_globale'),
    ]

    operations = [
        migrations.RunPython(_dedupliquer_lignes, _noop),
        migrations.AlterUniqueTogether(
            name='ligneremiseencaissement',
            unique_together=set(),
        ),
        migrations.AddConstraint(
            model_name='ligneremiseencaissement',
            constraint=models.UniqueConstraint(
                fields=('paiement',),
                name='uniq_ligne_remise_par_paiement'),
        ),
    ]
