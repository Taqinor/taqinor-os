"""CIQ130 — les réponses de catégorie commerciale deviennent des éléments
d'HORAIRE déclarés, jamais des coefficients.

Module PUR (aucun import Django, aucune base). Les réponses collectées par
catégorie (clés de ``COMMERCIAL_CATEGORY_QUESTIONS``, ``etude_params`` /
lead) ne changeaient que des phrases du PDF : une boulangerie qui cuit la
nuit, un restaurant du soir et une école fermée l'été recevaient le même
scalaire. Ici, une réponse ne produit QUE ce que le client a DIT :

* restaurant — ``horaires`` midi | soir | continu ⇒ plages, SEULEMENT avec
  les heures données (``heures`` : ``[[debut_h, fin_h], …]``) ; sinon
  alerte « heures d'ouverture à préciser » ;
* boulangerie — ``cuisson_nocturne`` + four ÉLECTRIQUE ⇒ plage nocturne
  (``heures_cuisson``) ; four au GAZ ⇒ aucune plage four sur la courbe
  électrique (la facture électrique reste la seule base) ;
* école — ``fermeture_estivale`` + dates (``fermeture_du`` / ``fermeture_au``)
  ⇒ fermeture ; sans dates ⇒ alerte ;
* santé — ``garde_nuit`` ⇒ plage de nuit (``heures_garde``) ; sans heures ⇒
  alerte ;
* hammam — chauffe au gaz ou au bois ⇒ aucune charge thermique ajoutée.

Les réponses de GRANDEUR (occupation, piscine, chambres, chambres froides,
effectif…) ne modifient PAS la courbe, faute de coefficient sourcé : elles sont
rendues dans ``non_consommees``.
"""

#: Réponses qui ne portent qu'une GRANDEUR (aucun coefficient sourcé).
REPONSES_GRANDEUR = frozenset({
    'occupation_pct', 'piscine', 'chambres', 'chambres_froides', 'effectif',
    'lits', 'surface_vente_m2', 'surface_m2', 'clim', 'internat',
    'temperature_consigne', 'volume_m3', 'saisonnalite_recolte',
})

#: Clés d'HEURES que le client donne (jamais supposées).
CLES_HEURES = ('heures', 'heures_cuisson', 'heures_garde')
CLES_DATES = ('fermeture_du', 'fermeture_au')


def _alerte(code, champ, message, niveau='alerte', interne=False):
    return {'code': code, 'champ': champ, 'message': message,
            'niveau': niveau, 'interne': interne}


def _vrai(valeur):
    return valeur is True or valeur in ('oui', 'true', 'True', 1)


def _plages(valeur):
    """``[[debut, fin], …]`` lisibles (0 ≤ h ≤ 24), sinon ``None``."""
    if not isinstance(valeur, (list, tuple)) or not valeur:
        return None
    sortie = []
    for plage in valeur:
        try:
            debut, fin = float(plage[0]), float(plage[1])
        except (TypeError, ValueError, IndexError):
            return None
        if not (0 <= debut <= 24 and 0 <= fin <= 24) or debut == fin:
            return None
        sortie.append([debut, fin])
    return sortie


def elements_horaire(categorie, reponses):
    """``(plages, fermetures, non_consommees, alertes)`` d'une catégorie.

    ``plages`` : ``{type_jour: [[debut_h, fin_h]]}`` (heure CIVILE, comme les
    plages saisies) ou ``None`` ; ``fermetures`` : ``[{du, au, motif}]``.
    """
    reponses = reponses if isinstance(reponses, dict) else {}
    plages = None
    fermetures = []
    alertes = []
    consommees = set()

    if categorie == 'restaurant' and reponses.get('horaires'):
        consommees.update({'horaires', 'heures'})
        heures = _plages(reponses.get('heures'))
        if heures:
            plages = {'ouvre': heures}
        else:
            alertes.append(_alerte(
                'heures_ouverture_a_preciser', 'rythme.reponses_categorie.heures',
                "Horaires « %s » déclarés : heures d'ouverture à préciser."
                % reponses.get('horaires')))
    elif categorie == 'boulangerie':
        consommees.update({'four', 'cuisson_nocturne', 'heures_cuisson'})
        four = reponses.get('four')
        if _vrai(reponses.get('cuisson_nocturne')) and four == 'electrique':
            heures = _plages(reponses.get('heures_cuisson'))
            if heures:
                plages = {'ouvre': heures}
            else:
                alertes.append(_alerte(
                    'heures_cuisson_a_preciser', 'rythme.reponses_categorie.heures_cuisson',
                    'Cuisson nocturne au four électrique : heures de cuisson à préciser.'))
        elif four == 'gaz':
            alertes.append(_alerte(
                'four_gaz', 'rythme.reponses_categorie.four',
                'Four au gaz : aucune charge de four sur la courbe électrique (la facture '
                'électrique reste la seule base).', niveau='info'))
    elif categorie == 'ecole' and _vrai(reponses.get('fermeture_estivale')):
        consommees.update({'fermeture_estivale', *CLES_DATES})
        du, au = reponses.get('fermeture_du'), reponses.get('fermeture_au')
        if du and au:
            fermetures.append({'du': du, 'au': au, 'motif': 'fermeture estivale déclarée'})
        else:
            alertes.append(_alerte(
                'dates_fermeture_a_preciser', 'rythme.reponses_categorie.fermeture_du',
                'Fermeture estivale déclarée : dates à préciser.'))
    elif categorie == 'sante' and _vrai(reponses.get('garde_nuit')):
        consommees.update({'garde_nuit', 'heures_garde'})
        heures = _plages(reponses.get('heures_garde'))
        if heures:
            plages = {'ouvre': heures, 'samedi': heures, 'dimanche': heures}
        else:
            alertes.append(_alerte(
                'heures_garde_a_preciser', 'rythme.reponses_categorie.heures_garde',
                'Garde de nuit déclarée : heures de garde à préciser.'))
    elif categorie == 'hammam':
        consommees.add('chauffe')
        if reponses.get('chauffe') in ('gaz', 'bois'):
            alertes.append(_alerte(
                'chauffe_non_electrique', 'rythme.reponses_categorie.chauffe',
                'Chauffe au %s : aucune charge thermique ajoutée à la courbe électrique.'
                % reponses.get('chauffe'), niveau='info'))

    non_consommees = sorted(k for k in reponses if k not in consommees
                            and (k in REPONSES_GRANDEUR or k not in CLES_HEURES))
    return plages, fermetures, non_consommees, alertes
