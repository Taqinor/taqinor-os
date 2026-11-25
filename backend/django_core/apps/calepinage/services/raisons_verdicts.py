"""T4-X9-002 — la RAISON courte d'un contrôle électrique échoué, dite à un commercial.

Le verdict détaillé (``electrique._verdict``) garde son libellé technique — le NOM du contrôle,
la condition à tenir (« Courant par entrée MPPT sous le courant admissible ») — et son détail
mesuré, que l'installateur lit. Collés dans la liste « Onduleur » (« … sous le courant
admissible (18,6 A au-dessus de la borne de fiche 18,0 A) »), ils se contredisaient. La raison
dit le FAIT et son SENS en une phrase, sans sigle : elle est servie sous la clé ``raison`` du
verdict (``None`` quand le contrôle passe ou n'est pas vérifiable).
"""
from __future__ import annotations

#: ``code -> (ce qui est mesuré, ce que l'onduleur admet)``, pour un dépassement par le HAUT
#: (``sens == 'sous'`` : la valeur devait rester sous la borne) puis par le BAS.
_RAISONS = {
    'courant_par_entree_mppt': (
        'le courant des panneaux ({v}) dépasse ce qu’une entrée de cet onduleur accepte ({b})', None),
    'voc_cold_under_vmax': (
        'par grand froid, la tension des panneaux ({v}) dépasse ce que cet onduleur supporte ({b})', None),
    'vmp_cold_under_mppt_max': (
        'par froid, la tension des panneaux ({v}) dépasse la plage de travail de cet onduleur ({b})', None),
    'vmp_hot_over_mppt_min': (
        None, 'par forte chaleur, la tension des panneaux ({v}) tombe sous la plage de travail de cet onduleur ({b})'),
}


def raison_du_verdict(code, valeur, borne, sens, unite):
    """La phrase du dépassement de ``code`` (``valeur`` contre ``borne``, en ``unite``), ou
    ``None`` pour un code sans phrase ou un sens inattendu."""
    from core.electrique.types import fr

    haut, bas = _RAISONS.get(code, (None, None))
    modele = haut if sens == 'sous' else bas
    if modele is None:
        return None
    return modele.format(v='%s %s' % (fr(valeur, 1), unite), b='%s %s' % (fr(borne, 1), unite))
