"""CAL71 — les dégagements d'obstacle, SAISIS par la société et JUSTIFIÉS.

LE CONSTAT
----------
Les dégagements autour d'un obstacle étaient des CONSTANTES de code de
l'atelier (``apps/web/src/scripts/roofPro11/types.ts`` ``CLEARANCE_BY_TYPE`` :
cheminée / chien-assis / édicule 0,50 m, ventilation / antenne / autre
0,30 m ; ``PERIMETER_SETBACK_M = 0.5`` dans ``apps/web/src/lib/roofPro2.ts``).
Aucune société ne pouvait les ajuster, et personne ne voyait d'où elles
venaient à l'écran.

CE QU'ELLES SONT, ET CE QU'ELLES NE SONT PAS
----------------------------------------------
**Ces valeurs n'ont AUCUNE source normative dans ce dépôt.** Le commentaire
qui les accompagne côté site explique un raisonnement de pose (suie et
ramonage pour une souche, accès pour une lucarne) — c'est une justification
d'atelier, pas un texte opposable. Elles s'affichent donc « valeur atelier
actuelle, non sourcée » tant que la société n'a pas saisi les siennes, même
discipline que CAL149 pour les profils et CAL74 pour les zones
réglementaires. Une valeur saisie par la société, elle, est annoncée comme
telle — et, si elle porte une source, la source est CITÉE.

OÙ ÇA VIT
---------
Dans la section ``degagements`` de ``ParametresCalepinage`` (CAL45) : AUCUN
nouveau modèle, AUCUNE migration. Le traducteur du document
(``services/traduction.py``, CAL78) consomme ce module, de sorte que modifier
un dégagement société change RÉELLEMENT le calepinage et la phrase de règle
affichée à côté de chaque obstacle — comme le moteur le fait déjà pour ses
propres règles (``core/calepinage/obstacles.py``, règle tracée).

ÉQUIVALENCE, GARANTIE PAR TEST : une société qui n'a rien saisi obtient les
chiffres d'aujourd'hui, au centimètre près.

ALLÉES DE CIRCULATION PAR PAYS (CALX402)
------------------------------------------
La clé ``allees_circulation`` de cette même section porte une largeur
d'allée de circulation SAISIE PAR PAYS — un besoin distinct de l'allée
technique unique ci-dessus (``CLE_ALLEE``). Parité marché : Aurora fait
dépendre cette largeur du code de l'autorité locale et publie 36 pouces
comme simple valeur usuelle américaine, modifiable. **Ce dépôt ne porte
AUCUNE largeur** — ni les 36 pouces américains, ni une règle DTU ou une
prescription des services d'incendie française : elles n'y sont pas. Un
pays non saisi n'obtient donc PAS de valeur par défaut : la circulation est
OMISE, en nommant le réglage qui manque (``largeur_allee_circulation``,
patron de ``allee_technique``).
"""
from __future__ import annotations

import re

from .parametres import ReglageInvalide

#: La section des réglages que ce module porte (CAL45).
SECTION = 'degagements'

#: Les types d'obstacle de l'atelier et leur dégagement ACTUEL (m), dans
#: l'ordre de ``CLEARANCE_BY_TYPE``. C'est un tuple et non un dict : c'est
#: une référence figée, pas une table qu'on mute.
DEGAGEMENTS_ATELIER = (
    ('cheminee', 0.50, 'Cheminée / souche'),
    ('ventilation', 0.30, 'Ventilation / VMC'),
    ('chien_assis', 0.50, 'Chien-assis / lucarne'),
    ('edicule', 0.50, 'Édicule / local technique'),
    ('antenne', 0.30, 'Antenne / parabole'),
    ('autre', 0.30, 'Autre'),
)

#: Dégagement de l'atelier pour un obstacle SANS type
#: (``OBSTACLE_CLEARANCE_M``).
DEGAGEMENT_ATELIER_DEFAUT_M = 0.30

#: Retrait de rive de l'atelier (``PERIMETER_SETBACK_M``). Même statut : c'est
#: la valeur appliquée aujourd'hui, pas une règle.
RETRAIT_ATELIER_M = 0.50

#: La clé du retrait de rive dans la section. C'est le nom PUBLIÉ par le
#: contrat ``contract_samples/parametres_calepinage.json`` (CAL45) : le
#: renommer casserait le contrat et les écrans qui le lisent.
CLE_RETRAIT = 'retrait_rive_m'

#: La clé de l'allée technique, elle aussi publiée par le contrat. Elle
#: alimente ``Parametres.allee_m`` du moteur quand la société l'a saisie ;
#: absente, le moteur garde son allée par défaut — comportement d'aujourd'hui.
CLE_ALLEE = 'allee_technique_m'

#: La clé (optionnelle) qui porte la SOURCE textuelle des valeurs de la
#: société. Absente, les valeurs saisies sont annoncées « réglage société »
#: sans citer de texte : on ne fabrique jamais une source.
CLE_SOURCE = 'source'

#: La phrase qui dit ce que vaut un chiffre non saisi. Écrite UNE fois : deux
#: formulations de la même réserve seraient deux réserves différentes.
MENTION_NON_SOURCEE = 'valeur atelier actuelle, non sourcée'

#: CALX402 — la clé des allées de circulation SAISIES par pays. Forme :
#: ``[{"pays": "ma", "largeur_m": 1.2, "source": "…", "reference": "…"}]``.
#: Publiée telle quelle par le contrat des réglages société.
CLE_ALLEES_CIRCULATION = 'allees_circulation'

#: Les quatre clés admises d'une entrée d'``allees_circulation`` — et
#: AUCUNE autre : on ne range pas un réglage dans un tiroir qui n'existe pas.
_CLES_ALLEE_CIRCULATION = ('pays', 'largeur_m', 'source', 'reference')

#: Même convention de code pays que CAL47 (``services/site.py``) : deux
#: lettres minuscules (ISO 3166-1 alpha-2), jamais devinée.
_PAYS_ALLEE = re.compile(r'^[a-z]{2}$')

__all__ = [
    'SECTION', 'DEGAGEMENTS_ATELIER', 'DEGAGEMENT_ATELIER_DEFAUT_M',
    'RETRAIT_ATELIER_M', 'CLE_RETRAIT', 'CLE_ALLEE', 'CLE_SOURCE',
    'MENTION_NON_SOURCEE', 'CLE_ALLEES_CIRCULATION', 'types_admis',
    'degagement_du_type', 'retrait_perimetre', 'allee_technique',
    '_largeur_allee_circulation', 'normaliser_section_degagements',
]


def types_admis():
    """Les types d'obstacle de l'atelier — jamais une liste recopiée."""
    return tuple(nom for nom, _valeur, _libelle in DEGAGEMENTS_ATELIER)


def _libelle(type_obstacle):
    for nom, _valeur, libelle in DEGAGEMENTS_ATELIER:
        if nom == type_obstacle:
            return libelle
    return type_obstacle


def _atelier(type_obstacle):
    for nom, valeur, _libelle in DEGAGEMENTS_ATELIER:
        if nom == type_obstacle:
            return valeur
    return DEGAGEMENT_ATELIER_DEFAUT_M


def _titre(cle):
    """Le libellé français d'une clé de la section, pour les messages."""
    if cle == CLE_RETRAIT:
        return 'Retrait de rive'
    if cle == CLE_ALLEE:
        return 'Allée technique'
    return _libelle(cle)


def _nombre(valeur, champ, libelle):
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
        raise ReglageInvalide(
            f"« {libelle} » doit être un nombre de mètres "
            f"(reçu : {type(valeur).__name__}).", champ=champ)
    if float(valeur) < 0:
        raise ReglageInvalide(
            f"« {libelle} » ne peut pas être négatif (reçu : {valeur}).",
            champ=champ)
    return float(valeur)


def normaliser_section_degagements(valeur):
    """La section ``degagements`` VALIDÉE.

    Forme admise — et AUCUNE autre clé, parce qu'on ne range pas un réglage
    dans un tiroir qui n'existe pas :

        {"cheminee": 0.6, …, "retrait_rive_m": 0.4,
         "allee_technique_m": 0.9, "source": "…",
         "allees_circulation": [{"pays": "ma", "largeur_m": 1.2,
                                  "source": "…", "reference": "…"}]}

    Les trois clés avant la dernière sont celles que le contrat publié
    (``contract_samples/parametres_calepinage.json``) déclare déjà : elles
    sont acceptées telles quelles, jamais renommées. ``allees_circulation``
    (CALX402) est une LISTE : chaque entrée porte SA propre provenance, une
    par pays, et une entrée sans ``source`` est refusée en nommant le champ
    (``allees_circulation[i].source``).

    Returns:
        ``{}`` quand la section est vide : ÉQUIVALENCE stricte — une société
        sans réglage se comporte exactement comme aujourd'hui.

    Raises:
        ReglageInvalide: clé inconnue, valeur qui n'est pas un nombre de
            mètres, ou valeur négative — le champ fautif est NOMMÉ.
    """
    if valeur is None:
        return {}
    if not isinstance(valeur, dict):
        raise ReglageInvalide(
            f"La section « {SECTION} » doit être un objet "
            f"(reçu : {type(valeur).__name__}).", champ=SECTION)
    if not valeur:
        return {}

    admises = types_admis() + (
        CLE_RETRAIT, CLE_ALLEE, CLE_ALLEES_CIRCULATION, CLE_SOURCE)
    inconnues = [str(cle) for cle in valeur if str(cle) not in admises]
    if inconnues:
        raise ReglageInvalide(
            f"Réglage de dégagement inconnu : « {', '.join(inconnues)} ». "
            f"Réglages admis : {', '.join(admises)}.",
            champ=f'{SECTION}.{inconnues[0]}')

    propre = {}
    for cle, brut in valeur.items():
        cle = str(cle)
        if cle == CLE_SOURCE:
            texte = str(brut or '').strip()
            if texte:
                propre[CLE_SOURCE] = texte
            continue
        if cle == CLE_ALLEES_CIRCULATION:
            propre[cle] = _allees_circulation(brut)
            continue
        propre[cle] = _nombre(brut, f'{SECTION}.{cle}', _titre(cle))
    return propre


def _allee_circulation_entree(brut, indice):
    """Une entrée ``{pays, largeur_m, source, reference}`` VALIDÉE (CALX402).

    ``reference`` est optionnelle (une valeur arrêtée par la société se
    défend par sa provenance) ; les trois autres clés sont obligatoires.
    Le champ fauté est nommé SANS le préfixe de section, sur le patron de
    l'entrée elle-même : ``allees_circulation[i].<clé>``.
    """
    prefixe = f'{CLE_ALLEES_CIRCULATION}[{indice}]'
    if not isinstance(brut, dict):
        raise ReglageInvalide(
            f"« {prefixe} » doit être un objet "
            "{pays, largeur_m, source, reference} "
            f"(reçu : {type(brut).__name__}).", champ=prefixe)

    surplus = sorted(set(brut) - set(_CLES_ALLEE_CIRCULATION))
    if surplus:
        raise ReglageInvalide(
            f"« {prefixe} » ne porte que pays, largeur_m, source et "
            f"reference (reçu en plus : {', '.join(surplus)}).",
            champ=f'{prefixe}.{surplus[0]}')

    pays = str(brut.get('pays') or '').strip().lower()
    if not pays or not _PAYS_ALLEE.match(pays):
        raise ReglageInvalide(
            f"« {prefixe}.pays » doit être un code pays à deux lettres "
            f"(reçu : {brut.get('pays')!r}).", champ=f'{prefixe}.pays')

    largeur = _nombre(brut.get('largeur_m'), f'{prefixe}.largeur_m',
                      "Largeur d'allée de circulation")
    if largeur <= 0:
        raise ReglageInvalide(
            f"« {prefixe}.largeur_m » doit être strictement positive "
            f"(reçu : {largeur}).", champ=f'{prefixe}.largeur_m')

    source = str(brut.get('source') or '').strip()
    if not source:
        raise ReglageInvalide(
            f"« {prefixe}.source » doit être renseignée : une largeur "
            "d'allée de circulation ne se défend pas sans sa provenance.",
            champ=f'{prefixe}.source')

    reference = brut.get('reference')
    if reference is None:
        reference = ''
    elif not isinstance(reference, str):
        raise ReglageInvalide(
            f"« {prefixe}.reference » doit être un texte "
            f"(reçu : {type(reference).__name__}).",
            champ=f'{prefixe}.reference')
    else:
        reference = reference.strip()

    return {'pays': pays, 'largeur_m': largeur, 'source': source,
            'reference': reference}


def _allees_circulation(brut):
    """La liste ``allees_circulation`` VALIDÉE — une entrée par pays.

    Returns:
        ``[]`` quand rien n'est saisi, sinon la liste PROPRE, chaque entrée
        ``{pays, largeur_m, source, reference}``.

    Raises:
        ReglageInvalide: pas une liste, entrée malformée, ou pays réglé
            deux fois (ambiguïté — lequel ferait foi ?).
    """
    if brut is None:
        return []
    if not isinstance(brut, list):
        raise ReglageInvalide(
            f"« {CLE_ALLEES_CIRCULATION} » doit être une liste "
            "{pays, largeur_m, source, reference} "
            f"(reçu : {type(brut).__name__}).",
            champ=CLE_ALLEES_CIRCULATION)

    propres = []
    vus = set()
    for indice, entree in enumerate(brut):
        propre = _allee_circulation_entree(entree, indice)
        if propre['pays'] in vus:
            raise ReglageInvalide(
                f"« {CLE_ALLEES_CIRCULATION}[{indice}].pays » : le pays "
                f"« {propre['pays']} » est déjà réglé par une entrée "
                "précédente.",
                champ=f'{CLE_ALLEES_CIRCULATION}[{indice}].pays')
        vus.add(propre['pays'])
        propres.append(propre)
    return propres


def _source(section):
    return str((section or {}).get(CLE_SOURCE) or '').strip()


def degagement_du_type(type_obstacle, section=None):
    """``(valeur, phrase)`` — le dégagement appliqué, et POURQUOI.

    Args:
        type_obstacle: le type de l'atelier (``cheminee``, ``antenne``…) ou
            ``None`` pour un obstacle sans type.
        section: la section ``degagements`` de la société. Absente ou muette
            sur ce type ⇒ la valeur de l'atelier, annoncée NON SOURCÉE.

    Returns:
        ``(mètres, phrase française)``. La phrase est faite pour être affichée
        TELLE QUELLE à côté de l'obstacle : un chiffre qui retire de la
        surface sans dire au nom de quoi est indéfendable.
    """
    section = section or {}
    nom = str(type_obstacle) if type_obstacle else ''
    libelle = _libelle(nom) if nom else 'Obstacle sans type'
    saisi = section.get(nom) if nom else None
    if isinstance(saisi, bool) or not isinstance(saisi, (int, float)):
        saisi = None

    if saisi is None:
        valeur = _atelier(nom) if nom else DEGAGEMENT_ATELIER_DEFAUT_M
        return (valeur, '%s : %.2f m (%s)'
                % (libelle, valeur, MENTION_NON_SOURCEE))

    source = _source(section)
    phrase = ('%s : %.2f m (réglage de votre société)'
              % (libelle, float(saisi)))
    if source:
        phrase = '%s : %.2f m (réglage de votre société — %s)' % (
            libelle, float(saisi), source)
    return (float(saisi), phrase)


def retrait_perimetre(section=None):
    """``(valeur, phrase)`` — le retrait de rive appliqué, et POURQUOI.

    Même discipline que ``degagement_du_type`` : la valeur de l'atelier est
    annoncée NON SOURCÉE tant que la société n'a pas saisi la sienne.
    """
    section = section or {}
    saisi = section.get(CLE_RETRAIT)
    if isinstance(saisi, bool) or not isinstance(saisi, (int, float)):
        return (RETRAIT_ATELIER_M,
                'Retrait de rive : %.2f m (%s)'
                % (RETRAIT_ATELIER_M, MENTION_NON_SOURCEE))
    source = _source(section)
    phrase = ('Retrait de rive : %.2f m (réglage de votre société)'
              % (float(saisi),))
    if source:
        phrase = ('Retrait de rive : %.2f m (réglage de votre société '
                  '— %s)' % (float(saisi), source))
    return (float(saisi), phrase)


def allee_technique(section=None):
    """``(valeur ou None, phrase)`` — l'allée technique saisie par la société.

    ``None`` quand la société n'a rien saisi : le moteur garde alors SON
    allée par défaut (``Parametres.allee_m``), comportement d'aujourd'hui.
    On ne fabrique pas ici une « allée de l'atelier » : le site ne trace pas
    d'allée technique, cette clé est propre aux réglages société.
    """
    section = section or {}
    saisi = section.get(CLE_ALLEE)
    if isinstance(saisi, bool) or not isinstance(saisi, (int, float)):
        return (None, "Allée technique : non réglée — l'allée par défaut du "
                      'moteur est appliquée.')
    source = _source(section)
    phrase = ('Allée technique : %.2f m (réglage de votre société)'
              % (float(saisi),))
    if source:
        phrase = ('Allée technique : %.2f m (réglage de votre société — %s)'
                  % (float(saisi), source))
    return (float(saisi), phrase)


def _largeur_allee_circulation(section, *, pays):
    """``(valeur ou None, phrase)`` — la largeur d'allée de circulation
    SAISIE par la société pour ``pays`` (CALX402), sur le patron de
    ``allee_technique``.

    Privée (fold lot 2, 21/09/2026) : le consommateur RÉEL de cette règle est
    l'atelier (`roofPro11/obstaclesUi.ts::largeurAlleeDepuisReglages`,
    CALX403), qui lit la section brute servie par ``GET calepinage/parametres/``.
    Aucune vue ni aucun service Django ne l'appelle encore : elle ne promet
    donc rien à personne (garde ``check_services_appeles``) et redeviendra
    publique le jour où un verdict serveur la consomme.

    Args:
        section: la section ``degagements`` de la société (ou ``None``).
        pays: le code pays (deux lettres, insensible à la casse) dont
            l'appelant veut la largeur — typiquement celui du site du
            calepinage en cours.

    Returns:
        ``(mètres, phrase)`` quand ce pays a une entrée dans
        ``allees_circulation`` ; ``(None, motif)`` sinon — le dépôt ne porte
        AUCUNE largeur de référence (ni les 36 pouces américains d'Aurora,
        ni une règle DTU ou une prescription incendie française) : un pays
        non saisi ne reçoit donc PAS de défaut, et ``motif`` NOMME le
        réglage manquant pour que l'appelant (CALX403, l'atelier) OMETTE la
        circulation en le citant, jamais en la forfaitisant.
    """
    code = str(pays or '').strip().lower()
    reglage = f'{SECTION}.{CLE_ALLEES_CIRCULATION}.{code or "?"}'

    if not code:
        return (None, 'Allée de circulation : aucun pays fourni — réglage '
                      f'manquant : {reglage}.')

    entrees = (section or {}).get(CLE_ALLEES_CIRCULATION)
    if not isinstance(entrees, list):
        entrees = []

    for entree in entrees:
        if not isinstance(entree, dict):
            continue
        if str(entree.get('pays') or '').strip().lower() != code:
            continue
        largeur = entree.get('largeur_m')
        if isinstance(largeur, bool) or not isinstance(largeur, (int, float)):
            break
        source = str(entree.get('source') or '').strip()
        reference = str(entree.get('reference') or '').strip()
        phrase = ('Allée de circulation (%s) : %.2f m (réglage de votre '
                  'société — %s)' % (code, float(largeur), source or
                                     'source non renseignée'))
        if reference:
            phrase = '%s, %s' % (phrase, reference)
        return (float(largeur), phrase)

    return (None, 'Allée de circulation (%s) : non réglée — aucune largeur '
                  "n'est saisie pour ce pays (réglage manquant : %s)."
                  % (code, reglage))
