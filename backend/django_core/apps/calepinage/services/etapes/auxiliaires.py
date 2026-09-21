"""CALX175 — ÉTAPE « auxiliaires » : une énergie SOUTIRÉE, jour et nuit.

CE QUI EXISTAIT, ET POURQUOI IL SE CONTREDISAIT
-------------------------------------------------
``services/pertes.py`` distingue déjà ``auxiliaires`` et
``auxiliaires_nocturnes``, et sa propre référence dit que c'est « une énergie
réellement soutirée, jamais un arrondi ». Pourtant ``pertes_politique.py``
n'accepte pour ces deux postes qu'un POURCENTAGE entre 0 et 100, comme pour
tous les autres : la saisie contredisait la définition. Un ventilateur, une
surveillance et un transformateur de service ne consomment pas un pourcentage
de ce que le champ produit — ils consomment des watts, y compris quand le
champ ne produit rien.

CE QUE CETTE ÉTAPE FAIT
-------------------------
Elle lit des PUISSANCES saisies et les convertit en énergie heure par heure :

* un terme CONSTANT en marche (W) ;
* un terme PROPORTIONNEL à la production (W par kW alternatif produit) ;
* une consommation de NUIT (W), lue sur la fiche de l'onduleur
  (``conso_nuit_w``, CALX60) quand le nombre d'onduleurs est connu, sinon
  saisie par la société.

C'est la décomposition de PVsyst : un terme constant au-dessus d'un seuil, un
terme proportionnel en W/kW, la consommation de nuit étant une valeur fixe
distincte (https://www.pvsyst.com/help/project-design/array-and-system-losses/
auxiliaries-consumption.html).

LE POURCENTAGE N'EST PLUS QU'UNE SORTIE
-----------------------------------------
``entree['pct_publie']`` est CALCULÉ — l'énergie auxiliaire rapportée à
l'énergie d'avant l'étape — et n'est jamais une saisie. Les heures sans
production voient leur puissance alternative devenir NÉGATIVE : c'est
exactement ce qui se passe, l'énergie est soutirée au réseau. Elle n'est donc
pas un arrondi, et elle n'est pas non plus le poste saisi
``auxiliaires_nocturnes`` : celui-ci reste HORS de la chaîne de production
(``chaine_pertes.POSTES_HORS_CHAINE``), parce qu'un pourcentage de la
production ne décrit pas une énergie de nuit.

CE QUI LA FAIT S'OMETTRE
--------------------------
Aucune des trois puissances saisie ⇒ étape OMISE en nommant les TROIS
champs. Série qui ne déclare pas encore le porteur alternatif (l'étape
« onduleur » ne s'est pas appliquée) ⇒ étape OMISE en le disant : les
auxiliaires se retranchent après la conversion, jamais sur du continu.
"""
from __future__ import annotations

from apps.calepinage.services import etapes

LIBELLE = 'Auxiliaires'

#: La colonne d'énergie qu'exige cette étape : l'alternatif de CALX170.
COLONNE_ALTERNATIVE = 'p_ac_kw'

#: Les trois clés de réglage société (registre CALX145, section
#: « simulation »), dans l'ordre où l'étape les nomme.
CLE_CONSTANTE = 'auxiliaires_w_constants'
CLE_PAR_KW = 'auxiliaires_w_par_kw'
CLE_NUIT = 'auxiliaires_w_nuit'

REFERENCE_PVSYST = (
    'PVsyst — Auxiliaries consumption : un terme constant au-dessus d\'un '
    'seuil et un terme proportionnel en W/kW, la consommation de nuit étant '
    'une valeur fixe distincte '
    '(https://www.pvsyst.com/help/project-design/array-and-system-losses/'
    'auxiliaries-consumption.html)')

MOTIF_SANS_PUISSANCE = (
    "Aucune puissance d'auxiliaires saisie : les trois champs « {constante} "
    "», « {par_kw} » et « {nuit} » sont vides, et la fiche de l'onduleur ne "
    "publie pas de consommation de nuit exploitable. L'étape est OMISE — un "
    "pourcentage ne décrit pas une énergie soutirée.")

MOTIF_SANS_ALTERNATIF = (
    "La série ne déclare pas de puissance alternative : les auxiliaires se "
    "retranchent APRÈS la conversion de l'onduleur (CALX170), jamais sur la "
    "puissance continue. Étape OMISE.")

__all__ = ['appliquer', 'LIBELLE', 'COLONNE_ALTERNATIVE', 'CLE_CONSTANTE',
           'CLE_PAR_KW', 'CLE_NUIT']


def appliquer(serie, contexte):
    """``(serie, etape)`` — l'énergie soutirée par les auxiliaires."""
    contexte = contexte if isinstance(contexte, dict) else {}

    if serie.get('colonne_energie') != COLONNE_ALTERNATIVE:
        return serie, etapes.etape_omise(
            LIBELLE, MOTIF_SANS_ALTERNATIF, champ='serie.colonne_energie')

    constante = _saisie(contexte, CLE_CONSTANTE)
    par_kw = _saisie(contexte, CLE_PAR_KW)
    nuit = _consommation_de_nuit(contexte)
    if constante is None and par_kw is None and nuit is None:
        return serie, etapes.etape_omise(
            LIBELLE,
            MOTIF_SANS_PUISSANCE.format(constante=CLE_CONSTANTE,
                                        par_kw=CLE_PAR_KW, nuit=CLE_NUIT),
            champ='%s / %s / %s' % (CLE_CONSTANTE, CLE_PAR_KW, CLE_NUIT))

    return _retirer(serie, constante, par_kw, nuit)


def _retirer(serie, constante, par_kw, nuit):
    """L'énergie auxiliaire, heure par heure, jour ET nuit."""
    heures = float(serie.get('pas_minutes') or etapes.PAS_MINUTES_PVGIS)
    heures = heures / 60.0
    w_constante = constante['valeur'] if constante else 0.0
    w_par_kw = par_kw['valeur'] if par_kw else 0.0
    w_nuit = nuit['valeur'] if nuit else 0.0

    points = []
    energie_avant = 0.0
    energie_jour = 0.0
    energie_nuit = 0.0
    heures_de_nuit = 0
    for point in serie.get('points') or []:
        puissance_kw = _nombre(point.get(COLONNE_ALTERNATIVE))
        if puissance_kw is None:
            points.append(point)
            continue
        if puissance_kw > 0.0:
            aux_w = w_constante + w_par_kw * puissance_kw
            energie_jour += aux_w * heures / 1000.0
        else:
            aux_w = w_nuit
            heures_de_nuit += 1
            energie_nuit += aux_w * heures / 1000.0
        copie = dict(point)
        copie[COLONNE_ALTERNATIVE] = puissance_kw - aux_w / 1000.0
        points.append(copie)
        energie_avant += puissance_kw * heures

    suite = dict(serie)
    suite['points'] = points
    suite['colonne_energie'] = COLONNE_ALTERNATIVE

    totale = energie_jour + energie_nuit
    pct = (100.0 * totale / energie_avant if energie_avant > 0.0 else None)
    return suite, etapes.etape_appliquee(
        LIBELLE,
        source=_source(constante, par_kw, nuit),
        entree={
            'champ': '%s / %s / %s' % (CLE_CONSTANTE, CLE_PAR_KW, CLE_NUIT),
            'w_constants': _publie(constante),
            'w_par_kw': _publie(par_kw),
            'w_nuit': _publie(nuit),
            'heures_de_nuit': heures_de_nuit,
            'energie_jour_kwh': round(energie_jour, 4),
            'energie_nuit_kwh': round(energie_nuit, 4),
            'energie_totale_kwh': round(totale, 4),
            'pct_publie': None if pct is None else round(pct, 4),
            'pct_est_une_sortie': "le pourcentage est CALCULÉ (énergie "
                                  "auxiliaire / énergie d'avant l'étape) et "
                                  "n'est jamais saisi",
        },
        reference=REFERENCE_PVSYST)


# ── les trois puissances, et d'où chacune vient ─────────────────────────

def _saisie(contexte, cle):
    """La puissance saisie pour ``cle``, ou ``None`` — jamais un défaut."""
    valeur = etapes.reglage(contexte, cle)
    if valeur is None:
        return None
    nombre = _nombre(valeur.get('valeur'))
    if nombre is None or nombre < 0.0:
        return None
    return {'valeur': nombre, 'source': valeur.get('source'),
            'origine': 'reglages_simulation.%s' % cle,
            'reference': valeur.get('reference') or ''}


def _consommation_de_nuit(contexte):
    """La consommation de nuit : la FICHE d'abord, la saisie ensuite.

    La fiche publie une consommation PAR ONDULEUR : elle n'est retenue que si
    le bloc électrique dit combien d'onduleurs sont posés. Sans ce nombre, on
    retombe sur la saisie société, qui est une valeur d'installation.
    """
    fiche_onduleur = contexte.get('fiche_onduleur') or {}
    unitaire = _nombre(fiche_onduleur.get('conso_nuit_w'))
    nombre = _nombre_d_onduleurs(contexte)
    if unitaire is not None and unitaire >= 0.0 and nombre:
        return {'valeur': unitaire * nombre, 'source': 'fiche',
                'origine': 'fiche_onduleur.conso_nuit_w',
                'reference': 'Fiche produit de l\'onduleur (CALX60), '
                             '%g onduleur(s)' % nombre}
    return _saisie(contexte, CLE_NUIT)


def _nombre_d_onduleurs(contexte):
    electrique = contexte.get('electrique')
    if not isinstance(electrique, dict):
        return None
    for onduleur in electrique.get('onduleurs') or ():
        if isinstance(onduleur, dict):
            nombre = _nombre(onduleur.get('nombre'))
            if nombre and nombre > 0.0:
                return nombre
    return None


def _source(*termes):
    """Les provenances RÉELLEMENT employées, sans doublon ni invention."""
    sources = []
    for terme in termes:
        if not terme:
            continue
        source = str(terme.get('source') or '').strip()
        if source and source not in sources:
            sources.append(source)
    return ' et '.join(sources)


def _publie(terme):
    """Ce qu'on publie d'un terme : sa valeur ET d'où elle vient."""
    if not terme:
        return None
    return {'valeur': terme['valeur'], 'source': terme['source'],
            'origine': terme['origine'], 'reference': terme['reference']}


def _nombre(valeur):
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None
