"""CALX174 — ÉTAPE « transformateur » : seulement si la société en déclare un.

LE CONSTAT
----------
``transformateur`` est au catalogue des postes (``services/pertes.py``) sans
calcul NI condition : le poste pouvait donc être saisi — et retranché — sur
une villa qui n'a aucun transformateur.

CE QUE CETTE ÉTAPE FAIT
------------------------
Elle ne s'applique QUE si un transformateur est déclaré dans l'entrée
électrique du calepinage (``contexte['entree_electrique']['transformateur']``
— la clé sous laquelle ``services/electrique.py`` range cette entrée). Deux
pertes y sont saisies SÉPARÉMENT, chacune avec sa source :

* la perte À VIDE — une puissance constante, tirée à TOUTES les heures, y
  compris la nuit ; c'est la définition même d'une perte à vide ;
* la perte EN CHARGE — les pertes cuivre, en I², donc proportionnelles au
  CARRÉ du taux de charge ``P / P_nominale`` ; elles sont nulles la nuit.

PVsyst range la perte de transformateur externe comme un poste de perte à
part entière de son diagramme
(https://www.pvsyst.com/help/project-design/array-and-system-losses/
index.html).

CE QUI LA FAIT SE TAIRE
------------------------
* Aucun transformateur déclaré ⇒ étape omise avec un motif NEUTRE (« aucun
  transformateur dans cette installation ») et AUCUN champ à saisir : ce
  n'est pas un oubli, il n'y a donc rien à signaler à l'utilisateur.
* Transformateur déclaré mais pertes non saisies ⇒ étape omise en nommant
  LES DEUX champs.
* Pertes saisies mais puissance nominale absente ⇒ omise en nommant la
  puissance : sans elle, le taux de charge — et donc la loi en I² — n'existe
  pas.

LA NUIT, LE BILAN PEUT DEVENIR NÉGATIF
---------------------------------------
Une heure sans production qui porte quand même la perte à vide sort en
énergie NÉGATIVE : c'est une énergie réellement soutirée, et elle est
conservée telle quelle plutôt que ramenée à zéro — un plancher à zéro
effacerait une consommation qui existe.

Module PUR : aucune base, aucun réseau.
"""
from __future__ import annotations

from apps.calepinage.services import etapes as _etapes

#: La clé sous laquelle ``services/electrique.py`` range l'entrée électrique
#: du calepinage, et celle du transformateur à l'intérieur.
CLE_ENTREE = 'entree_electrique'
CLE_TRANSFORMATEUR = 'transformateur'

#: Les trois grandeurs saisies, chacune ``{valeur, source, reference}``.
CHAMP_A_VIDE = 'perte_a_vide_kw'
CHAMP_EN_CHARGE = 'perte_en_charge_kw_nominale'
CHAMP_NOMINAL = 'puissance_nominale_kw'

MOTIF_ABSENT = (
    'Aucun transformateur dans cette installation : le poste ne la concerne '
    'pas et rien ne reste à renseigner.')

REFERENCE = (
    'PVsyst — Array and system losses : la perte de transformateur externe '
    'est un poste de perte à part entière du diagramme '
    '(https://www.pvsyst.com/help/project-design/array-and-system-losses/'
    'index.html).')

LIBELLE = 'Transformateur'

__all__ = ['CLE_ENTREE', 'CLE_TRANSFORMATEUR', 'CHAMP_A_VIDE',
           'CHAMP_EN_CHARGE', 'CHAMP_NOMINAL', 'MOTIF_ABSENT', 'REFERENCE',
           'LIBELLE', 'appliquer']


def appliquer(serie, contexte):
    """``(serie, etape)`` — à vide + en charge, ou un silence neutre."""
    contexte = contexte if isinstance(contexte, dict) else {}
    declaration = _declaration(contexte)
    if declaration is None:
        return serie, _etapes.etape_omise(LIBELLE, MOTIF_ABSENT)

    a_vide = _saisie(declaration, CHAMP_A_VIDE)
    en_charge = _saisie(declaration, CHAMP_EN_CHARGE)
    manquants = [nom for nom, saisie in ((CHAMP_A_VIDE, a_vide),
                                         (CHAMP_EN_CHARGE, en_charge))
                 if saisie is None]
    if manquants:
        return serie, _etapes.etape_omise(
            LIBELLE,
            'Un transformateur est déclaré, mais ses pertes ne sont pas '
            'saisies : la perte à vide et la perte en charge se saisissent '
            'séparément, chacune avec sa source. '
            f'Non renseigné(s) : {_liste(manquants)}.',
            champ=_champ(manquants))

    nominal = _saisie(declaration, CHAMP_NOMINAL)
    if nominal is None or nominal['valeur'] <= 0:
        return serie, _etapes.etape_omise(
            LIBELLE,
            'La puissance nominale du transformateur n\'est pas saisie : '
            'sans elle, le taux de charge de chaque heure — et donc la perte '
            'cuivre en I² — ne peut pas être calculé.',
            champ=_champ([CHAMP_NOMINAL]))

    rendue, heures, energie_a_vide, energie_en_charge = _appliquer(
        serie, a_vide['valeur'], en_charge['valeur'], nominal['valeur'])
    entree = {
        CHAMP_A_VIDE: a_vide,
        CHAMP_EN_CHARGE: en_charge,
        CHAMP_NOMINAL: nominal,
        'heures': heures,
        'energie_a_vide_kwh': _arrondi(energie_a_vide),
        'energie_en_charge_kwh': _arrondi(energie_en_charge),
        'loi_en_charge': 'perte cuivre en I² : (P / P_nominale)²',
        'perte_a_vide_la_nuit': True,
    }
    return rendue, _etapes.etape_appliquee(
        LIBELLE, source=a_vide['source'], entree=entree, reference=REFERENCE)


# ── la déclaration, LUE de l'entrée électrique ─────────────────────────

def _declaration(contexte):
    """Le transformateur déclaré, ou ``None`` s'il n'y en a pas.

    Un ``declare: False`` explicite vaut « pas de transformateur » : une
    société qui a répondu la question ne doit pas être re-questionnée.
    """
    entree = contexte.get(CLE_ENTREE)
    if not isinstance(entree, dict):
        return None
    declare = entree.get(CLE_TRANSFORMATEUR)
    if declare is True:
        return {}
    if not isinstance(declare, dict) or not declare:
        return None
    if declare.get('declare') is False:
        return None
    return declare


def _saisie(declaration, champ):
    """``{valeur, source, reference}`` lisible et sourcé, ou ``None``.

    Une valeur sans source n'est pas une valeur saisie (D-CALX 7) : le champ
    ressort comme non renseigné, et il est nommé.
    """
    brut = declaration.get(champ)
    if not isinstance(brut, dict):
        return None
    valeur = _nombre(brut.get('valeur'))
    source = (brut.get('source') or '').strip()
    if valeur is None or valeur < 0 or not source:
        return None
    return {'valeur': valeur, 'source': source,
            'reference': brut.get('reference') or ''}


def _liste(champs):
    return ', '.join(f'« {nom} »' for nom in champs)


def _champ(champs):
    return ' et '.join(f'{CLE_ENTREE}.{CLE_TRANSFORMATEUR}.{nom}'
                       for nom in champs)


# ── l'application, heure par heure ─────────────────────────────────────

def _appliquer(serie, a_vide_kw, en_charge_kw, nominal_kw):
    """Copie PURE : à vide partout, en charge en I², et le détail publié."""
    colonne = _etapes.colonne_energie(serie)
    pas_minutes = serie.get('pas_minutes') or _etapes.PAS_MINUTES_PVGIS
    heures_du_pas = float(pas_minutes) / 60.0
    rendus = []
    heures = 0
    energie_a_vide = 0.0
    energie_en_charge = 0.0
    for point in (serie or {}).get('points') or ():
        if not isinstance(point, dict):
            rendus.append(point)
            continue
        copie = dict(point)
        heures += 1
        if colonne is None:
            rendus.append(copie)
            continue
        facteur = _etapes.FACTEURS_KW[colonne]
        brut = _nombre(point.get(colonne))
        if brut is None:
            rendus.append(copie)
            continue
        puissance_kw = brut * facteur
        charge = puissance_kw / nominal_kw
        perte_en_charge = en_charge_kw * charge * charge
        copie[colonne] = (puissance_kw - a_vide_kw - perte_en_charge) \
            / facteur
        energie_a_vide += a_vide_kw * heures_du_pas
        energie_en_charge += perte_en_charge * heures_du_pas
        rendus.append(copie)
    rendue = dict(serie)
    rendue['points'] = rendus
    if colonne is not None:
        rendue['colonne_energie'] = colonne
    return rendue, heures, energie_a_vide, energie_en_charge


def _arrondi(valeur):
    return round(valeur, 3)


def _nombre(valeur):
    if isinstance(valeur, bool):
        return None
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        return None
    if nombre != nombre:
        return None
    return nombre
