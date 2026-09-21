"""CAL74 — servitudes et bandes coupe-feu : des zones SOURCÉES, jamais devinées.

LE CONSTAT, ÉCRIT NOIR SUR BLANC DANS LE DÉPÔT
-----------------------------------------------
Le dépôt ne contient AUCUN texte normatif marocain, et la documentation du
moteur le dit elle-même (``docs/moteur-calepinage.md`` : pas de génération
automatique d'exclusions réglementaires). Les outils du marché proposent des
retraits réglementaires par région — mais ils s'appuient sur un corpus que
nous n'avons pas. Inventer une bande coupe-feu « standard » de 0,90 m parce
que ça se fait ailleurs, c'est livrer un plan qu'aucun texte ne défend.

LA DÉCISION
-----------
La société ENREGISTRE ses propres gabarits de zone réglementaire, dans la
section ``zones_types`` de ``ParametresCalepinage`` (CAL45 — AUCUN nouveau
modèle, AUCUNE migration), et **une SOURCE textuelle est OBLIGATOIRE** :

* sans source saisie, le gabarit N'EST PAS ENREGISTRÉ — refus français, sous
  le champ fautif (``zones_types.<clé>.source``) ;
* aucune largeur n'a de valeur par défaut : une bande sans ``largeur_m``
  saisie est refusée, elle n'est pas « supposée » ;
* la source VOYAGE avec la zone appliquée (clé ``source`` de la zone du
  document, schéma v2 ``exclusionZones``), pour que la planche et le PDF la
  CITENT à côté de la zone. Une zone qui retire de la surface sans dire au nom
  de quoi est indéfendable devant un client comme devant un contrôleur.

ÉQUIVALENCE : une société sans gabarit garde ``zones_types: {}`` — comportement
d'aujourd'hui, strictement inchangé.

APPLIQUER UN GABARIT ne change rien tout seul : ``appliquer_modele`` RENVOIE
une zone au format ``exclusionZones`` (CAL68) que l'écran bibliothèque
(CAL201) insère dans le document. Ce module n'écrit ni layout ni statut.
"""
from __future__ import annotations

from .parametres import ReglageInvalide

#: La section des réglages que ce module porte (CAL45).
SECTION = 'zones_types'

#: Les genres de géométrie RELATIVE admis pour un gabarit.
#:
#: * ``bande`` — une bande de largeur SAISIE le long d'un côté (ou de tout le
#:   périmètre) : la forme d'une servitude ou d'une bande coupe-feu ;
#: * ``polygone`` — un contour relatif saisi point par point, pour les cas que
#:   la bande ne décrit pas.
GENRES = ('bande', 'polygone')

#: Les côtés admis pour une bande. ``perimetre`` = tout le tour.
COTES = ('nord', 'sud', 'est', 'ouest', 'perimetre')

#: CALX104 câblage — les FORMES d'un gabarit d'OBSTACLE (l'atelier les lit dans
#: ``roofPro11/types.ts::lireGabaritsObstacle``). ``rectangle`` est la forme par
#: défaut de l'atelier ; aucune n'est supposée à la place d'une autre.
FORMES_OBSTACLE = ('rectangle', 'cercle', 'polygone')

#: Les clés d'un gabarit. Aucune autre n'est admise (on ne range pas un
#: réglage dans un tiroir qui n'existe pas).
#:
#: CALX104 câblage — ``type``, ``forme``, ``longueur_m`` et ``rayon_m`` ont été
#: AJOUTÉES : l'atelier lisait déjà ces quatre clés pour proposer les gabarits
#: d'OBSTACLE de la société, mais la porte d'enregistrement les refusait comme
#: « réglage inconnu ». Aucune société ne pouvait donc enregistrer un gabarit
#: d'obstacle, et le code qui les lit n'avait aucune donnée à lire. Les gabarits
#: de ZONE (bande / polygone) sont strictement inchangés : ces quatre clés sont
#: OPTIONNELLES et ne sont écrites que si elles sont saisies.
CLES = ('libelle', 'nature', 'genre', 'largeur_m', 'cote', 'sommets',
        'retrait_m', 'hauteur_m', 'source',
        'type', 'forme', 'longueur_m', 'rayon_m')

__all__ = ['SECTION', 'GENRES', 'COTES', 'CLES', 'FORMES_OBSTACLE',
           'normaliser_section_zones_types', 'appliquer_modele',
           'source_de_zone']


def _refus(message, champ):
    return ReglageInvalide(message, champ=champ)


def _texte(valeur, champ, libelle, *, obligatoire=False):
    if valeur is None or not isinstance(valeur, str) or not valeur.strip():
        if obligatoire:
            raise _refus(f"« {libelle} » est obligatoire.", champ)
        return None
    return valeur.strip()


def _nombre(valeur, champ, libelle, *, obligatoire=False):
    if valeur is None:
        if obligatoire:
            raise _refus(
                f"« {libelle} » est obligatoire : aucune valeur par défaut "
                "n'est supposée.", champ)
        return None
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
        raise _refus(
            f"« {libelle} » doit être un nombre en mètres "
            f"(reçu : {type(valeur).__name__}).", champ)
    if float(valeur) <= 0 and obligatoire:
        raise _refus(
            f"« {libelle} » doit être strictement positive "
            f"(reçu : {valeur}).", champ)
    if float(valeur) < 0:
        raise _refus(
            f"« {libelle} » ne peut pas être négative (reçu : {valeur}).",
            champ)
    return float(valeur)


def _nature(valeur, champ):
    from core.calepinage.types import NatureZone

    texte = _texte(valeur, champ, 'Nature', obligatoire=True)
    admises = tuple(n.value for n in NatureZone)
    if texte not in admises:
        raise _refus(
            f"Nature de zone inconnue : « {texte} ». Natures admises : "
            f"{', '.join(admises)}.", champ)
    return texte


def _type_obstacle(valeur, champ):
    """CALX104 — le type d'obstacle SAISI, ou ``None``.

    Les types admis sont ceux de l'atelier (``services/degagements.py``,
    ``DEGAGEMENTS_ATELIER``) : c'est la même table que celle qui porte leur
    dégagement, on n'en tient pas une seconde.
    """
    from .degagements import DEGAGEMENTS_ATELIER

    texte = _texte(valeur, champ, "Type d'obstacle")
    if texte is None:
        return None
    admis = tuple(cle for cle, _, _ in DEGAGEMENTS_ATELIER)
    if texte not in admis:
        raise _refus(
            f"Type d'obstacle inconnu : « {texte} ». Types admis : "
            f"{', '.join(admis)}.", champ)
    return texte


def _forme_obstacle(valeur, champ):
    """CALX104 — la forme SAISIE du gabarit d'obstacle, ou ``None``."""
    texte = _texte(valeur, champ, 'Forme')
    if texte is None:
        return None
    if texte not in FORMES_OBSTACLE:
        raise _refus(
            f"Forme de gabarit inconnue : « {texte} ». Formes admises : "
            f"{', '.join(FORMES_OBSTACLE)}.", champ)
    return texte


def _sommets(valeur, champ):
    if not isinstance(valeur, list) or len(valeur) < 3:
        raise _refus(
            "Un gabarit « polygone » demande au moins 3 sommets relatifs "
            "(x, y en mètres).", champ)
    propres = []
    for point in valeur:
        if (not isinstance(point, (list, tuple)) or len(point) < 2
                or any(isinstance(v, bool) or not isinstance(v, (int, float))
                       for v in point[:2])):
            raise _refus(
                f"Sommet relatif illisible (reçu : {point!r}).", champ)
        propres.append([float(point[0]), float(point[1])])
    return propres


def _modele(cle, brut):
    """UN gabarit validé, ou un refus qui nomme SON champ."""
    racine = f'{SECTION}.{cle}'
    if not isinstance(brut, dict):
        raise _refus(
            f"Le gabarit « {cle} » doit être un objet "
            f"(reçu : {type(brut).__name__}).", racine)

    inconnues = sorted(set(brut) - set(CLES))
    if inconnues:
        raise _refus(
            f"Réglage inconnu dans le gabarit « {cle} » : "
            f"« {', '.join(inconnues)} ». Réglages admis : "
            f"{', '.join(CLES)}.", f'{racine}.{inconnues[0]}')

    # LA RÈGLE DE LA TÂCHE : sans source, pas d'enregistrement. Le refus est
    # posé AVANT le reste pour que le message qui remonte soit CELUI-LÀ.
    source = _texte(brut.get('source'), f'{racine}.source',
                    'Source (texte, article, note de service)')
    if source is None:
        raise _refus(
            f"Le gabarit « {cle} » ne peut pas être enregistré sans SOURCE : "
            "indiquez le texte, l'article ou la note qui impose cette zone "
            "(le dépôt ne contient aucun corpus réglementaire, donc rien "
            "n'est supposé à votre place).", f'{racine}.source')

    genre = _texte(brut.get('genre'), f'{racine}.genre', 'Genre',
                   obligatoire=True)
    if genre not in GENRES:
        raise _refus(
            f"Genre de gabarit inconnu : « {genre} ». Genres admis : "
            f"{', '.join(GENRES)}.", f'{racine}.genre')

    modele = {
        'libelle': _texte(brut.get('libelle'), f'{racine}.libelle',
                          'Libellé') or cle,
        'nature': _nature(brut.get('nature'), f'{racine}.nature'),
        'genre': genre,
        'largeur_m': None,
        'cote': '',
        'sommets': [],
        'retrait_m': _nombre(brut.get('retrait_m'), f'{racine}.retrait_m',
                             'Retrait') or 0.0,
        'hauteur_m': _nombre(brut.get('hauteur_m'), f'{racine}.hauteur_m',
                             'Hauteur'),
        'source': source,
    }

    if genre == 'bande':
        # Largeur SAISIE, jamais un « standard » repris d'ailleurs.
        modele['largeur_m'] = _nombre(
            brut.get('largeur_m'), f'{racine}.largeur_m',
            'Largeur de la bande', obligatoire=True)
        cote = _texte(brut.get('cote'), f'{racine}.cote', 'Côté')
        if cote is not None and cote not in COTES:
            raise _refus(
                f"Côté de bande inconnu : « {cote} ». Côtés admis : "
                f"{', '.join(COTES)}.", f'{racine}.cote')
        # « perimetre » n'est pas une valeur DEVINÉE : c'est le seul repli qui
        # ne restreint rien (tout le tour), et il est documenté comme tel.
        modele['cote'] = cote or 'perimetre'
    else:
        modele['sommets'] = _sommets(brut.get('sommets'),
                                     f'{racine}.sommets')

    # CALX104 câblage — les quatre clés du gabarit d'OBSTACLE. Elles sont
    # OPTIONNELLES et ne sont posées QUE si elles ont été saisies : un gabarit
    # de zone enregistré avant cette tâche se relit octet pour octet.
    type_obstacle = _type_obstacle(brut.get('type'), f'{racine}.type')
    if type_obstacle is not None:
        modele['type'] = type_obstacle
    forme = _forme_obstacle(brut.get('forme'), f'{racine}.forme')
    if forme is not None:
        modele['forme'] = forme
    longueur_m = _nombre(brut.get('longueur_m'), f'{racine}.longueur_m',
                         'Longueur du gabarit')
    if longueur_m is not None:
        modele['longueur_m'] = longueur_m
    rayon_m = _nombre(brut.get('rayon_m'), f'{racine}.rayon_m',
                      'Rayon du gabarit')
    if rayon_m is not None:
        modele['rayon_m'] = rayon_m
    return modele


def normaliser_section_zones_types(valeur):
    """La section ``zones_types`` VALIDÉE : ``{clé: gabarit}``.

    Returns:
        ``{}`` si la section est vide — ÉQUIVALENCE : une société sans gabarit
        se comporte exactement comme aujourd'hui.

    Raises:
        ReglageInvalide: message FRANÇAIS nommant le champ fautif (et le
            gabarit concerné), à commencer par la SOURCE manquante.
    """
    if valeur is None:
        return {}
    if not isinstance(valeur, dict):
        raise _refus(
            f"La section « {SECTION} » doit être un objet "
            f"(reçu : {type(valeur).__name__}).", SECTION)
    if not valeur:
        return {}
    return {str(cle): _modele(str(cle), brut)
            for cle, brut in valeur.items()}


def appliquer_modele(modele, *, cle='', repere='', sommets=None):
    """UN gabarit -> une zone au format ``exclusionZones`` (CAL68).

    Args:
        modele: le gabarit normalisé (tel qu'il est stocké).
        cle / repere: l'identifiant de la zone posée (``repere`` prime).
        sommets: le contour RÉEL, calculé par l'écran à partir de l'emprise
            et de la largeur du gabarit. ``None`` pour un gabarit
            ``polygone``, qui porte déjà son contour relatif.

    Returns:
        La zone de document, PORTANT SA SOURCE — c'est cette clé que la
        planche et le PDF citent à côté de la zone. Rien n'est écrit ici :
        l'écran insère la zone dans ``roof_layout['exclusionZones']``.

    Raises:
        ReglageInvalide: un gabarit sans source ne peut pas être appliqué (il
            n'aurait pas dû pouvoir être enregistré non plus).
    """
    modele = modele or {}
    source = _texte(modele.get('source'), 'source', 'Source')
    if source is None:
        raise _refus(
            "Ce gabarit de zone n'a pas de source : il ne peut pas être "
            "appliqué (une zone qui retire de la surface doit dire au nom de "
            "quoi).", 'source')

    contour = sommets
    if contour is None:
        contour = modele.get('sommets')
    # Un contour VIDE n'est pas un contour : un gabarit « bande » ne porte que
    # sa largeur, c'est l'écran qui calcule le tracé réel depuis l'emprise.
    # Rendre une zone à zéro sommet la ferait passer pour posée alors qu'elle
    # ne bloquerait rien.
    if not isinstance(contour, list) or len(contour) < 3:
        raise _refus(
            "Ce gabarit ne porte pas de contour exploitable : fournissez le "
            "contour réel calculé depuis l'emprise et la largeur saisie "
            f"({modele.get('largeur_m')} m).", 'sommets')

    return {
        'id': repere or cle or modele.get('libelle') or 'ZONE',
        'label': modele.get('libelle') or cle or 'Zone réglementaire',
        'nature': modele.get('nature'),
        'vertices': [list(point) for point in contour],
        'setbackM': modele.get('retrait_m') or 0.0,
        'heightM': modele.get('hauteur_m'),
        'source': source,
    }


def source_de_zone(zone):
    """La SOURCE à citer à côté d'une zone, ou ``''``.

    Une zone sans source rend une chaîne vide : la planche affiche alors la
    zone SANS citation plutôt qu'une citation inventée. C'est la règle « zéro
    chiffre, zéro référence inventée » appliquée au texte.
    """
    return _texte((zone or {}).get('source'), 'source', 'Source') or ''
