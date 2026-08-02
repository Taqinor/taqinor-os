# Écrite À LA MAIN (YDATA15) : `makemigrations` ne tourne pas sur cette
# machine (WeasyPrint n'y trouve pas libgobject-2.0). Le contenu suit le style
# de 0019_economie.py et a été vérifié par l'autodétecteur de Django, qui ne
# voit plus aucune différence entre les modèles et ces migrations.
#
# Deux des quatre tables visées SONT DÉJÀ EN PRODUCTION (``compta_bordereauprix``
# et ``compta_lignebordereau``, reprises de compta par ao/0001) : y poser un
# unique d'un seul coup est exactement le piège déjà payé une fois en prod.
# Chaque contrainte à risque est donc précédée d'une remise en ordre des
# éventuels doublons existants. Les deux autres tables (``ao_toiture``,
# ``ao_obstacle``) naissent de migrations non encore déployées : rien à réparer.

import itertools
import string

from django.db import migrations, models


def _indices_candidats():
    """A, B, C… puis R1, R2… — assez court pour ``max_length=4``."""
    for lettre in string.ascii_uppercase:
        yield lettre
    for rang in itertools.count(1):
        yield 'R%d' % rang


def _degrouper_bordereaux(apps, schema_editor):
    """Deux bordereaux jumeaux sous le même indice SONT deux révisions.

    Le modèle le dit : « deux bordereaux d'indices différents ne sont jamais le
    même document ». Un doublon hérité est donc réparé en donnant au plus récent
    le premier indice LIBRE — jamais en supprimant ni en renommant un intitulé
    que quelqu'un a écrit.
    """
    Bordereau = apps.get_model('ao', 'BordereauPrix')
    vus = set()
    for bordereau in list(Bordereau.objects.order_by('appel_offre_id', 'id')):
        cle = (bordereau.appel_offre_id, bordereau.intitule,
               bordereau.indice_revision)
        if cle not in vus:
            vus.add(cle)
            continue
        for indice in _indices_candidats():
            candidat = (bordereau.appel_offre_id, bordereau.intitule, indice)
            if candidat in vus:
                continue
            bordereau.indice_revision = indice
            bordereau.save(update_fields=['indice_revision'])
            vus.add(candidat)
            break


def _renumeroter_lignes(apps, schema_editor):
    """Renumérote 1..N les bordereaux dont des lignes partagent un n°.

    C'est la remise en ordre qu'exige déjà le contrôle
    ``AO_NUMEROTATION_BORDEREAU`` (numérotation contiguë) : le n° de ligne par
    défaut valant 1, un bordereau saisi sans n° explicite portait N lignes « 1 ».
    Seuls les bordereaux réellement en doublon sont touchés.
    """
    Ligne = apps.get_model('ao', 'LigneBordereau')
    vus, a_reprendre = set(), set()
    for bordereau_id, numero in Ligne.objects.values_list('bordereau_id',
                                                          'numero'):
        if (bordereau_id, numero) in vus:
            a_reprendre.add(bordereau_id)
        vus.add((bordereau_id, numero))
    for bordereau_id in sorted(a_reprendre):
        lignes = list(Ligne.objects.filter(bordereau_id=bordereau_id)
                      .order_by('numero', 'id'))
        for rang, ligne in enumerate(lignes, 1):
            if ligne.numero != rang:
                ligne.numero = rang
                ligne.save(update_fields=['numero'])


class Migration(migrations.Migration):

    dependencies = [
        ('ao', '0020_alter_lignecoutrevient_prix_unitaire_ht'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='toitureao',
            constraint=models.UniqueConstraint(condition=models.Q(('code_document', ''), _negated=True), fields=('batiment', 'code_document'), name='uniq_toiture_code_document'),
        ),
        migrations.AddConstraint(
            model_name='obstacleao',
            constraint=models.UniqueConstraint(condition=models.Q(('repere', ''), _negated=True), fields=('toiture', 'repere'), name='uniq_obstacle_repere_par_toiture'),
        ),
        migrations.RunPython(_degrouper_bordereaux,
                             migrations.RunPython.noop, elidable=True),
        migrations.AddConstraint(
            model_name='bordereauprix',
            constraint=models.UniqueConstraint(fields=('appel_offre', 'intitule', 'indice_revision'), name='uniq_bordereau_intitule_indice'),
        ),
        migrations.RunPython(_renumeroter_lignes,
                             migrations.RunPython.noop, elidable=True),
        migrations.AddConstraint(
            model_name='lignebordereau',
            constraint=models.UniqueConstraint(fields=('bordereau', 'numero'), name='uniq_ligne_bordereau_numero'),
        ),
    ]
