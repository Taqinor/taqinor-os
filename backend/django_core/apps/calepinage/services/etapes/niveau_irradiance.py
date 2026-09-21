"""CALX162 — l'étape « niveau d'irradiance » : le faible éclairement, lu sur
la COURBE de la fiche du module, ou rien du tout.

CE QUE LE DÉPÔT AVAIT, ET POURQUOI ÇA NE SUFFISAIT PAS
--------------------------------------------------------
``services/pertes.py`` porte le poste ``irradiance`` au catalogue depuis
toujours, mais personne ne le CALCULE : il ne se saisit qu'en pourcentage.
Côté fiche, le seul rendement publié était celui du STC
(``rendement_pct``) — un module ne rend pourtant pas le même pourcentage
sous 1000 W/m² et sous 150 W/m². CALX60 a ouvert le champ
``FicheTechnique.rendement_par_irradiance`` ; cette étape est son premier
lecteur.

CE QU'ELLE LIT, ET RIEN D'AUTRE
---------------------------------
* ``contexte['fiche_module']['rendement_par_irradiance']`` — la courbe
  PUBLIÉE par le constructeur : des paires ``{w_m2, rendement_relatif_pct}``
  d'abscisse strictement croissante, le rendement étant RELATIF (% du
  rendement STC). Absente ⇒ étape OMISE en nommant le champ et le module
  concerné (D-CALX 7 : jamais un forfait, jamais un 0 %).
* ``serie['points'][i]['gi_w_m2']`` — l'irradiance sur le plan des modules,
  telle que ``services/pvgis_serie.py`` la publie. Aucun point lisible ⇒
  étape OMISE en nommant la colonne.

CE QU'ELLE NE FAIT PAS : EXTRAPOLER
-------------------------------------
La courbe n'est interpolée qu'ENTRE les points publiés. Une irradiance
au-delà du dernier point retient la DERNIÈRE valeur publiée ; une irradiance
en deçà du premier retient la PREMIÈRE. Prolonger la pente au-delà des
bornes reviendrait à inventer un chiffre que le constructeur n'a pas publié —
la ``reference`` de l'étape DIT combien de points ont été retenus ainsi, et à
quelles bornes, pour que personne ne lise une extrapolation là où il n'y en a
aucune.

CE QU'ELLE ASSUME, ET LE DIT
------------------------------
L'irradiance lue est celle que la série PORTE à ce rang de la cascade. Les
étapes amont (horizon, ombrage, salissure…) retirent aujourd'hui de
l'ÉNERGIE sans réécrire ``gi_w_m2`` : le niveau d'irradiance est donc évalué
sur l'irradiance du plan, non sur l'irradiance effective après ombres. Le
jour où une étape amont republiera ``gi_w_m2``, cette étape la lira sans
changer d'une ligne.

PARITÉ
--------
PVsyst fait découler la perte de niveau d'irradiance de son modèle à une
diode, où la résistance série pèse fortement sur la performance à faible
éclairement :
https://www.pvsyst.com/help/component-database/photovoltaics-modules/modules-in-the-database/index.html
Nous n'avons pas ce modèle : nous n'utilisons que ce que le constructeur a
publié, et nous nous taisons quand il n'a rien publié.
"""
from __future__ import annotations

from apps.calepinage.services import etapes

#: Le champ de fiche lu, sous le nom que ``apps.stock.selectors``
#: (``specs_for_produit``, CALX60) publie.
CHAMP_COURBE = 'rendement_par_irradiance'

#: Le champ tel qu'on le NOMME à l'écran quand il manque — l'utilisateur va
#: le chercher sur la fiche technique, pas dans un dict de specs.
CHAMP_AFFICHE = f'FicheTechnique.{CHAMP_COURBE}'

#: La colonne d'irradiance de la série horaire (CALX142 / pvgis_serie).
COLONNE_IRRADIANCE = 'gi_w_m2'

#: Les deux clés d'un point de la courbe publiée (CALX60).
CLE_ABSCISSE = 'w_m2'
CLE_ORDONNEE = 'rendement_relatif_pct'

#: La référence doctrinale citée par l'étape appliquée.
REFERENCE = (
    'PVsyst — modèle à une diode : la résistance série pèse sur la '
    'performance à faible éclairement '
    '(https://www.pvsyst.com/help/component-database/photovoltaics-modules/'
    'modules-in-the-database/index.html). Ici, aucun modèle : uniquement la '
    'courbe publiée par le constructeur.')

MOTIF_COURBE_ABSENTE = (
    "Aucune courbe de rendement à éclairement partiel n'est publiée sur la "
    'fiche de {produit} : le rendement de la fiche est celui du STC seul, et '
    "rien ne permet de dire ce que le module rend sous faible éclairement. "
    "L'étape est OMISE — aucun forfait n'est appliqué à sa place.")

MOTIF_POINT_ILLISIBLE = (
    'La courbe de rendement à éclairement partiel de {produit} porte un '
    'point illisible au rang {index} : un point doit publier « {abscisse} » '
    "(W/m²) et « {ordonnee} » (% du rendement STC). L'étape est OMISE plutôt "
    "que calculée sur une courbe qu'on ne sait pas lire.")

MOTIF_ORDRE_ROMPU = (
    "La courbe de rendement à éclairement partiel de {produit} n'est pas "
    "strictement croissante en abscisse au rang {index} : l'interpolation "
    "serait ambiguë. L'étape est OMISE plutôt que calculée sur une courbe "
    'remise en ordre à la volée.')

MOTIF_IRRADIANCE_ABSENTE = (
    "La série horaire ne porte aucune irradiance lisible : sans elle, le "
    'niveau auquel lire la courbe de {produit} est inconnu. '
    "L'étape est OMISE.")

MOTIF_ENERGIE_ILLISIBLE = (
    "Aucune colonne d'énergie lisible dans la série ({colonnes}) : il n'y a "
    'rien à quoi appliquer le rendement relatif de {produit}. '
    "L'étape est OMISE.")

__all__ = ['CHAMP_COURBE', 'CHAMP_AFFICHE', 'COLONNE_IRRADIANCE',
           'CLE_ABSCISSE', 'CLE_ORDONNEE', 'REFERENCE', 'appliquer']


def appliquer(serie, contexte):
    """``(serie, etape)`` — le contrat de ``services/etapes/__init__.py``.

    Fonction PURE : la série reçue n'est jamais modifiée sur place, et
    l'étape omise la rend telle quelle.
    """
    contexte = contexte if isinstance(contexte, dict) else {}
    fiche_module = contexte.get('fiche_module') or {}
    produit = _produit_designe(contexte)
    libelle = _libelle()

    courbe, motif = _courbe_lisible(_courbe_publiee(fiche_module), produit)
    if motif:
        return serie, etapes.etape_omise(libelle, motif, champ=CHAMP_AFFICHE)
    if not courbe:
        return serie, etapes.etape_omise(
            libelle, MOTIF_COURBE_ABSENTE.format(produit=produit),
            champ=CHAMP_AFFICHE)

    colonne = etapes.colonne_energie(serie)
    if colonne is None:
        return serie, etapes.etape_omise(
            libelle,
            MOTIF_ENERGIE_ILLISIBLE.format(
                produit=produit,
                colonnes=', '.join(etapes.ORDRE_COLONNES_ENERGIE)))

    suite, compte = _appliquer_courbe(serie, colonne, courbe)
    if not compte['lus']:
        return serie, etapes.etape_omise(
            libelle, MOTIF_IRRADIANCE_ABSENTE.format(produit=produit),
            champ=COLONNE_IRRADIANCE)

    return suite, etapes.etape_appliquee(
        libelle,
        source='fiche',
        entree=CHAMP_COURBE,
        reference=_reference(produit, courbe, compte))


# ── la courbe : lue, jamais devinée ─────────────────────────────────────

def _courbe_publiee(fiche_module):
    """La courbe telle que la fiche la publie, ou ``None``.

    ``specs_for_produit`` rend un DICT de specs ; un double d'essai peut
    porter un objet. Les deux lectures nomment la même clé publiée par
    CALX60, et une clé absente vaut ``None`` — donc étape omise.
    """
    if isinstance(fiche_module, dict):
        return fiche_module.get('rendement_par_irradiance')
    return getattr(fiche_module, 'rendement_par_irradiance', None)


def _courbe_lisible(brute, produit):
    """``(points triés, motif)`` — ``motif`` non vide nomme le rang fautif.

    Aucun tri, aucune correction : une courbe qu'on ne sait pas lire fait
    OMETTRE l'étape en nommant son rang, elle n'est jamais rafistolée.
    """
    if brute is None:
        return [], ''
    if not isinstance(brute, (list, tuple)) or not brute:
        return [], ''

    points = []
    for index, point in enumerate(brute):
        if isinstance(point, dict):
            abscisse = point.get(CLE_ABSCISSE)
            ordonnee = point.get(CLE_ORDONNEE)
        elif isinstance(point, (list, tuple)) and len(point) == 2:
            abscisse, ordonnee = point
        else:
            return [], _motif_point(produit, index)
        abscisse = _nombre(abscisse)
        ordonnee = _nombre(ordonnee)
        if abscisse is None or ordonnee is None:
            return [], _motif_point(produit, index)
        if points and abscisse <= points[-1][0]:
            return [], MOTIF_ORDRE_ROMPU.format(produit=produit, index=index)
        points.append((abscisse, ordonnee))
    return points, ''


def _motif_point(produit, index):
    return MOTIF_POINT_ILLISIBLE.format(
        produit=produit, index=index, abscisse=CLE_ABSCISSE,
        ordonnee=CLE_ORDONNEE)


def _rendement_relatif(courbe, irradiance):
    """``(rendement relatif en %, position)`` à cette irradiance.

    ``position`` vaut ``'sous'``, ``'dans'`` ou ``'au_dessus'`` : c'est ce
    qui permet à la ``reference`` de DIRE combien de points ont été retenus
    aux bornes au lieu d'être extrapolés.
    """
    if irradiance <= courbe[0][0]:
        return courbe[0][1], 'sous'
    if irradiance >= courbe[-1][0]:
        return courbe[-1][1], 'au_dessus'
    precedent = courbe[0]
    for suivant in courbe[1:]:
        if irradiance <= suivant[0]:
            largeur = suivant[0] - precedent[0]
            part = (irradiance - precedent[0]) / largeur
            return (precedent[1] + part * (suivant[1] - precedent[1]),
                    'dans')
        precedent = suivant
    return courbe[-1][1], 'au_dessus'


# ── l'application, point par point ──────────────────────────────────────

def _appliquer_courbe(serie, colonne, courbe):
    """Une COPIE de la série dont chaque point porte son rendement relatif.

    Un point sans irradiance lisible ressort INCHANGÉ et il est COMPTÉ :
    le supprimer ou le mettre à zéro inventerait une production.
    """
    compte = {'lus': 0, 'sans_irradiance': 0, 'sous': 0, 'au_dessus': 0}
    points = []
    for point in serie.get('points') or []:
        if not isinstance(point, dict):
            points.append(point)
            continue
        irradiance = _nombre(point.get(COLONNE_IRRADIANCE))
        if irradiance is None:
            compte['sans_irradiance'] += 1
            points.append(point)
            continue
        compte['lus'] += 1
        relatif, position = _rendement_relatif(courbe, irradiance)
        if position in compte:
            compte[position] += 1
        valeur = _nombre(point.get(colonne))
        if valeur is None:
            points.append(point)
            continue
        copie = dict(point)
        copie[colonne] = valeur * relatif / 100.0
        points.append(copie)

    suite = dict(serie)
    suite['points'] = points
    suite['colonne_energie'] = colonne
    return suite, compte


def _reference(produit, courbe, compte):
    """La provenance de l'étape, ET ce que la courbe n'a PAS extrapolé."""
    bornes = (
        f'Courbe publiée sur la fiche de {produit}, de '
        f'{_texte(courbe[0][0])} à {_texte(courbe[-1][0])} W/m² '
        f'({len(courbe)} points).')
    hors = []
    if compte['sous']:
        hors.append(
            f"{compte['sous']} heure(s) sous {_texte(courbe[0][0])} W/m² : "
            f'la PREMIÈRE valeur publiée ({_texte(courbe[0][1])} %) est '
            'retenue')
    if compte['au_dessus']:
        hors.append(
            f"{compte['au_dessus']} heure(s) au-delà de "
            f'{_texte(courbe[-1][0])} W/m² : la DERNIÈRE valeur publiée '
            f'({_texte(courbe[-1][1])} %) est retenue')
    if compte['sans_irradiance']:
        hors.append(
            f"{compte['sans_irradiance']} heure(s) sans irradiance lisible : "
            'laissées inchangées')
    if hors:
        extrapolation = ('Aucune extrapolation hors des bornes publiées — '
                         + ' ; '.join(hors) + '.')
    else:
        extrapolation = ('Aucune extrapolation hors des bornes publiées : '
                         'toutes les heures lues tombent dans la courbe.')
    return f'{bornes} {extrapolation} {REFERENCE}'


# ── les petites lectures ────────────────────────────────────────────────

def _produit_designe(contexte):
    """Le nom du module PV tel que le document le porte, ou un repli.

    ``designations`` est la table que ``services/electrique.py`` compose
    déjà pour nommer le matériel retenu ; absente, l'étape parle du « module
    retenu » plutôt que d'un produit qu'elle ne connaît pas.
    """
    designations = contexte.get('designations')
    if isinstance(designations, dict):
        nom = (designations.get('module') or '').strip()
        if nom:
            return nom
    return 'le module retenu'


def _libelle():
    from apps.calepinage.services.chaine_pertes import LIBELLES
    return LIBELLES['niveau_irradiance']


def _nombre(valeur):
    """``float(valeur)`` quand c'est un nombre, sinon ``None``.

    Les Decimal des champs de fiche passent par ici ; un texte, un ``None``
    ou un booléen n'entrent jamais dans un calcul.
    """
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None


def _texte(valeur):
    """Un nombre écrit court : ``150`` plutôt que ``150.0``."""
    entier = int(valeur)
    return str(entier) if float(entier) == float(valeur) else str(valeur)
