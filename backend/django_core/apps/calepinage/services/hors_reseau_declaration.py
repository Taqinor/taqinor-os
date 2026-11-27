"""ACAL790 — la forme de la déclaration hors réseau (validation).

Extraite de ``services/electrique.py`` (ACAL166, ``_valider_hors_reseau``) à
comportement égal, puis complétée du contrôle des ``seuils`` de protection
(CALX272) : un seuil illisible s'enregistrait et OMETTAIT ensuite tout le
bloc hors réseau à la simulation. La règle d'ordre (arrêt ≤ entretien ≤
veille, chacun de 0 à 100 %) reste UNIQUE : celle de
``services/hors_reseau.py::_seuils_de_protection``, rejouée ici.
"""
from __future__ import annotations

from . import groupe_appoint as _groupe_appoint
from .valeurs import nombre as _nombre

__all__ = ['CLES_HORS_RESEAU', 'valider_hors_reseau']

#: ACAL166 — les clés d'une déclaration hors réseau (``etapes/hors_reseau.py``).
CLES_HORS_RESEAU = ('actif', 'jours_autonomie', 'etat_initial_kwh', 'seuils',
                    'groupe')


def valider_hors_reseau(saisie):
    """ACAL166 — la FORME du mode hors réseau : ``actif`` booléen, jours
    d'autonomie strictement positifs ; ACAL790 — ``seuils`` ordonnés.
    Refus nommé ``hors_reseau.<champ>``."""
    from .electrique import _fini, _refus_champ

    if saisie is None:
        return []
    if not isinstance(saisie, dict):
        _refus_champ("« hors_reseau » doit être un objet {actif, "
                     "jours_autonomie…} (reçu : %s)."
                     % type(saisie).__name__, 'hors_reseau')
    inconnues = sorted(set(saisie) - set(CLES_HORS_RESEAU))
    if inconnues:
        _refus_champ("Champ hors réseau inconnu : « %s ». Champs admis : %s."
                     % (inconnues[0], ', '.join(CLES_HORS_RESEAU)),
                     'hors_reseau.%s' % inconnues[0])
    if 'actif' in saisie and not isinstance(saisie['actif'], bool):
        _refus_champ("« actif » vaut vrai (hors réseau) ou faux (raccordé).",
                     'hors_reseau.actif')
    jours = saisie.get('jours_autonomie')
    if jours not in (None, ''):
        nombre = _nombre(jours)
        if not _fini(nombre) or nombre <= 0:
            _refus_champ("« jours_autonomie » : saisissez un nombre de jours "
                         "strictement positif (reçu : « %s »)." % jours,
                         'hors_reseau.jours_autonomie')
    etat = saisie.get('etat_initial_kwh')
    if etat not in (None, ''):
        nombre = _nombre(etat)
        if not _fini(nombre) or nombre < 0:
            _refus_champ("« etat_initial_kwh » : saisissez un nombre positif "
                         "ou nul (reçu : « %s »)." % etat,
                         'hors_reseau.etat_initial_kwh')
    _valider_seuils(saisie.get('seuils'), _refus_champ)
    _groupe_appoint.valider_groupe(saisie.get('groupe'), _refus_champ)  # ACAL800
    return _avertir_demarrage(saisie.get('seuils'), saisie.get('groupe'))


def _avertir_demarrage(seuils, groupe):
    """ACAL1667 — AVERTIT (jamais un refus) quand le groupe démarre sous la
    veille : la déclaration reste enregistrée telle quelle."""
    if not (isinstance(seuils, dict) and isinstance(groupe, dict)
            and groupe.get('actif')):
        return []
    demarrage = _nombre(groupe.get('soc_demarrage_pct'))
    veille = _nombre(seuils.get('veille_pct'))
    if demarrage is None or veille is None or demarrage >= veille:
        return []
    return ['Le groupe démarre sous le seuil de veille : il ne tournera '
            'jamais (démarrage à %g %%, veille à %g %%).'
            % (demarrage, veille)]


def _valider_seuils(seuils, refuser):
    """ACAL790 — ``seuils`` par la règle de calcul ; ``None`` efface."""
    from .hors_reseau import HorsReseauInvalide, _seuils_de_protection

    try:
        _seuils_de_protection(seuils)
    except HorsReseauInvalide as refus:
        refuser(refus.motif, 'hors_reseau.%s' % (refus.champ or 'seuils'))
