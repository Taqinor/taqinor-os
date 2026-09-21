"""CALX170 — ÉTAPE « onduleur » : la courbe η(P), sinon le rendement européen.

CE QUI EXISTAIT, ET POURQUOI IL NE SUFFISAIT PAS
-------------------------------------------------
``onduleur`` était un poste de catalogue SAISI en pourcentage, et la fiche ne
portait qu'un rendement européen unique — une moyenne pondérée, pas le
rendement de l'heure qu'on calcule. Aucun service ne convertissait une
puissance continue horaire en alternatif. PV*SOL écrit la conversion
``P_AC = P_DC · η_nominal · η_relatif``, où le rendement relatif est une
COURBE de la puissance d'entrée
(https://help.valentin-software.com/pvsol/en/calculation/inverters/) ;
CALX60 a ajouté le champ qui la porte, publié sous ``rendement_par_charge``.

TROIS CAS, DÉCLARÉS DANS CET ORDRE
------------------------------------
1. **La courbe** ``fiche_onduleur['rendement_par_charge']`` — des paires
   (% de la puissance nominale, η %), INTERPOLÉES linéairement entre deux
   points publiés. Jamais extrapolées : au-delà du dernier point publié ou en
   deçà du premier, la valeur publiée la plus proche est TENUE, et le nombre
   d'heures concernées est publié (``heures_hors_courbe``). Une courbe
   publiée par tension d'entrée (PV*SOL en publie une par tension) est
   choisie sur la tension de la chaîne ; si cette tension est inconnue et que
   plusieurs courbes existent, l'étape s'omet plutôt que d'en élire une.
2. **Le rendement européen** ``rendement_euro_pct``, appliqué à plat, le
   motif publié disant que c'est une valeur UNIQUE et non une courbe.
3. **L'omission**, en nommant ``FicheTechnique.ond_rendement_euro_pct`` et le
   produit concerné.

LE CHANGEMENT DE PORTEUR D'ÉNERGIE
------------------------------------
C'est ici que le continu devient de l'alternatif : la série rendue DÉCLARE
``colonne_energie = 'p_ac_kw'`` et chaque point porte sa valeur (``None`` là
où la puissance continue de l'heure est illisible : une donnée absente ne
devient pas un zéro). Les étapes suivantes (écrêtage, ohmique AC,
auxiliaires) lisent donc l'alternatif sans avoir à le deviner.

CE QUI N'EST PAS COMPTÉ ICI
-----------------------------
La consommation de nuit / de veille de l'onduleur est une énergie réellement
soutirée, en watts : elle appartient à l'étape « auxiliaires » (CALX175) et
n'est jamais comptée deux fois.
"""
from __future__ import annotations

from apps.calepinage.services import etapes

LIBELLE = 'Rendement onduleur'

#: La colonne d'énergie que cette étape POSE sur la série qu'elle rend.
COLONNE_SORTIE = 'p_ac_kw'

#: Le champ de fiche que l'omission nomme (le nom de la COLONNE du modèle,
#: celui que l'écran de fiche affiche).
CHAMP_FICHE_RENDEMENT = 'FicheTechnique.ond_rendement_euro_pct'

REFERENCE_PVSOL = (
    'PV*SOL — Inverters : P_AC = P_DC · η_nominal · η_relatif, le rendement '
    'relatif étant une courbe de la puissance d\'entrée '
    '(https://help.valentin-software.com/pvsol/en/calculation/inverters/)')

MOTIF_VALEUR_UNIQUE = (
    "Aucune courbe de rendement n'est publiée sur la fiche : le rendement "
    "européen est une valeur UNIQUE, une moyenne pondérée de la norme, "
    "appliquée à plat à chaque heure. Elle ne distingue pas une heure à "
    "pleine charge d'une heure à 10 % de charge.")

MOTIF_SANS_RENDEMENT = (
    "La fiche de l'onduleur {produit} ne publie ni courbe de rendement ni "
    "rendement européen : la conversion du continu en alternatif n'est pas "
    "calculable et l'étape est OMISE. Aucun rendement n'est supposé.")

MOTIF_PLUSIEURS_COURBES = (
    "La fiche publie une courbe de rendement PAR TENSION d'entrée, et la "
    "tension de la chaîne n'est pas connue : l'étape est OMISE plutôt que "
    "d'élire une courbe au hasard. Il y faut le Vmp de la fiche module et le "
    "nombre de modules par chaîne (bloc « electrique.chainage »).")

MOTIF_SERIE_ILLISIBLE = (
    "Aucune colonne d'énergie lisible sur la série : il n'y a pas de "
    "puissance continue à convertir. Étape OMISE.")

MOTIF_SANS_PUISSANCE_NOMINALE = (
    "La puissance nominale de l'onduleur n'est pas connue (ni « dc_max_kwc "
    "» ni « ac_kw » sur la fiche, ou aucun nombre d'onduleurs au bloc « "
    "electrique.onduleurs ») : la courbe η(P) n'a pas d'abscisse sur "
    "laquelle se poser. Étape OMISE.")

__all__ = ['appliquer', 'LIBELLE', 'COLONNE_SORTIE',
           'CHAMP_FICHE_RENDEMENT']


def appliquer(serie, contexte):
    """``(serie, etape)`` — le continu converti en alternatif, heure par heure."""
    contexte = contexte if isinstance(contexte, dict) else {}

    colonne = etapes.colonne_energie(serie)
    if colonne is None:
        return serie, etapes.etape_omise(LIBELLE, MOTIF_SERIE_ILLISIBLE)

    fiche_onduleur = contexte.get('fiche_onduleur') or {}
    courbe = _courbe(fiche_onduleur.get('rendement_par_charge'),
                     _tension_chaine_v(contexte))
    if isinstance(courbe, str):
        return serie, etapes.etape_omise(
            LIBELLE, courbe,
            champ='fiche_onduleur.rendement_par_charge')

    if courbe:
        nominale = _puissance_nominale_kw(contexte, fiche_onduleur)
        if nominale is None:
            return serie, etapes.etape_omise(
                LIBELLE, MOTIF_SANS_PUISSANCE_NOMINALE,
                champ='fiche_onduleur.dc_max_kwc')
        return _convertir_par_courbe(serie, colonne, courbe, nominale)

    euro = _nombre(fiche_onduleur.get('rendement_euro_pct'))
    if euro is None or euro <= 0.0:
        return serie, etapes.etape_omise(
            LIBELLE,
            MOTIF_SANS_RENDEMENT.format(produit=_produit(contexte)),
            champ=CHAMP_FICHE_RENDEMENT)
    return _convertir_a_plat(serie, colonne, euro)


# ── les deux conversions ─────────────────────────────────────────────────

def _convertir_par_courbe(serie, colonne, courbe, nominale):
    """La courbe η(P), interpolée entre deux points publiés."""
    facteur_kw = etapes.FACTEURS_KW[colonne]
    points = []
    hors_courbe = 0
    charge_min = courbe[0][0]
    charge_max = courbe[-1][0]

    for point in serie.get('points') or []:
        copie = dict(point)
        puissance_kw = _puissance_kw(point.get(colonne), facteur_kw)
        if puissance_kw is None:
            copie[COLONNE_SORTIE] = None
            points.append(copie)
            continue
        charge_pct = 100.0 * puissance_kw / nominale['valeur_kw']
        if charge_pct < charge_min or charge_pct > charge_max:
            hors_courbe += 1
        rendement = _interpoler(courbe, charge_pct)
        copie[COLONNE_SORTIE] = puissance_kw * rendement / 100.0
        points.append(copie)

    return _rendre(serie, points, {
        'champ': 'fiche_onduleur.rendement_par_charge',
        'modele': 'courbe η(P) interpolée, jamais extrapolée',
        'points_publies': len(courbe),
        'charge_min_pct': charge_min,
        'charge_max_pct': charge_max,
        'heures_hors_courbe': hors_courbe,
        'puissance_nominale_kw': round(nominale['valeur_kw'], 3),
        'base_puissance_nominale': nominale['base'],
        'hors_courbe_tenu': "la valeur publiée la plus proche est tenue ; "
                            "aucune droite n'est prolongée au-delà de la "
                            "courbe",
    })


def _convertir_a_plat(serie, colonne, rendement_pct):
    """Le rendement européen, valeur UNIQUE appliquée à chaque heure."""
    facteur_kw = etapes.FACTEURS_KW[colonne]
    points = []
    for point in serie.get('points') or []:
        copie = dict(point)
        puissance_kw = _puissance_kw(point.get(colonne), facteur_kw)
        copie[COLONNE_SORTIE] = (None if puissance_kw is None
                                 else puissance_kw * rendement_pct / 100.0)
        points.append(copie)

    return _rendre(serie, points, {
        'champ': 'fiche_onduleur.rendement_euro_pct',
        'modele': 'rendement européen appliqué à plat',
        'rendement_pct': rendement_pct,
        'motif': MOTIF_VALEUR_UNIQUE,
    })


def _rendre(serie, points, entree):
    """La série ALTERNATIVE, dont la colonne d'énergie est DÉCLARÉE."""
    suite = dict(serie)
    suite['points'] = points
    suite['colonne_energie'] = COLONNE_SORTIE
    return suite, etapes.etape_appliquee(
        LIBELLE, source='fiche', entree=entree, reference=REFERENCE_PVSOL)


# ── la courbe : lecture, choix de la tension, interpolation ─────────────

def _courbe(brute, tension_chaine_v):
    """Les paires ``(charge %, η %)`` triées, ``()`` si aucune courbe,
    ou un MOTIF d'omission (chaîne) quand la courbe est inexploitable."""
    if not isinstance(brute, (list, tuple)) or not brute:
        return ()

    series = {}
    for point in brute:
        if not isinstance(point, dict):
            continue
        charge = _nombre(point.get('charge_pct'))
        rendement = _nombre(point.get('rendement_pct'))
        if charge is None or rendement is None:
            continue
        series.setdefault(point.get('tension_v'), []).append(
            (charge, rendement))
    series = {cle: sorted(valeurs) for cle, valeurs in series.items()
              if valeurs}
    if not series:
        return ()
    if len(series) == 1:
        return tuple(next(iter(series.values())))

    if tension_chaine_v is None:
        return MOTIF_PLUSIEURS_COURBES
    tensions = [cle for cle in series if _nombre(cle) is not None]
    if not tensions:
        return MOTIF_PLUSIEURS_COURBES
    proche = min(tensions,
                 key=lambda cle: abs(_nombre(cle) - tension_chaine_v))
    return tuple(series[proche])


def _interpoler(courbe, charge_pct):
    """Le rendement à cette charge — interpolé, jamais extrapolé."""
    if charge_pct <= courbe[0][0]:
        return courbe[0][1]
    if charge_pct >= courbe[-1][0]:
        return courbe[-1][1]
    precedent = courbe[0]
    for point in courbe[1:]:
        if charge_pct <= point[0]:
            largeur = point[0] - precedent[0]
            if largeur <= 0.0:
                return point[1]
            part = (charge_pct - precedent[0]) / largeur
            return precedent[1] + part * (point[1] - precedent[1])
        precedent = point
    return courbe[-1][1]


# ── lectures de contexte ─────────────────────────────────────────────────

def _puissance_nominale_kw(contexte, fiche_onduleur):
    """La puissance nominale de l'ENSEMBLE des onduleurs, et sa base."""
    nombre = _nombre_d_onduleurs(contexte)
    if nombre is None:
        return None
    for cle, base in (('dc_max_kwc', 'puissance continue maximale de la '
                                     'fiche (dc_max_kwc)'),
                      ('ac_kw', 'puissance alternative nominale de la fiche '
                                '(ac_kw)')):
        unitaire = _nombre(fiche_onduleur.get(cle))
        if unitaire and unitaire > 0.0:
            return {'valeur_kw': unitaire * nombre, 'base': base,
                    'nombre_onduleurs': nombre}
    return None


def _nombre_d_onduleurs(contexte):
    """Le nombre d'onduleurs retenus, ou ``None`` si le bloc ne le dit pas."""
    electrique = contexte.get('electrique')
    if not isinstance(electrique, dict):
        return None
    for onduleur in electrique.get('onduleurs') or ():
        if isinstance(onduleur, dict):
            nombre = _nombre(onduleur.get('nombre'))
            if nombre and nombre > 0.0:
                return nombre
    return None


def _tension_chaine_v(contexte):
    """La tension de la chaîne au STC, ou ``None``."""
    fiche_module = contexte.get('fiche_module') or {}
    vmp = _nombre(fiche_module.get('vmp_v'))
    electrique = contexte.get('electrique')
    chainage = (electrique.get('chainage')
                if isinstance(electrique, dict) else None)
    modules = _nombre((chainage or {}).get('modules_par_chaine'))
    if not vmp or not modules:
        return None
    return vmp * modules


def _produit(contexte):
    """La désignation de l'onduleur, pour que l'omission NOMME le produit."""
    materiel = contexte.get('materiel')
    if isinstance(materiel, dict):
        designations = materiel.get('designations')
        if isinstance(designations, dict):
            nom = str(designations.get('onduleur') or '').strip()
            if nom:
                return '« %s »' % nom
    electrique = contexte.get('electrique')
    if isinstance(electrique, dict):
        for onduleur in electrique.get('onduleurs') or ():
            if isinstance(onduleur, dict):
                nom = str(onduleur.get('reference') or '').strip()
                if nom:
                    return '« %s »' % nom
    return 'retenu'


def _puissance_kw(valeur, facteur_kw):
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        return float(valeur) * facteur_kw
    except (TypeError, ValueError):
        return None


def _nombre(valeur):
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None
