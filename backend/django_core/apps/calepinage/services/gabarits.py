"""CAL82 — enregistrer et réappliquer des GABARITS de disposition.

LE CONSTAT
----------
L'atelier n'a aucun gabarit (un ``grep template|gabarit|preset`` sur
``roofPro11/`` ne rend que des presets de CONSOMMATION), alors que l'AO a
depuis longtemps ses presets de calepinage côté modèle. Résultat : chaque
nouvelle zone se règle à la main, et deux zones du même chantier finissent
réglées différemment sans que personne ne l'ait décidé.

CE QU'UN GABARIT PORTE — ET CE QU'IL NE PORTERA JAMAIS
--------------------------------------------------------
Un gabarit porte des RÈGLES DE POSE : orientation du module, famille de table,
rives, allée, mode de dimensionnement, priorité d'application. **Il ne porte
JAMAIS de géométrie de toit** — ni contour, ni obstacle, ni panneau posé, ni
épingle. C'est la garantie centrale de cette tâche : un gabarit appliqué à une
zone vierge règle sa POSE, il ne lui donne pas la forme d'un autre toit. Une
clé de géométrie glissée dans un gabarit est donc REFUSÉE en la nommant, pas
silencieusement ignorée — ignorée, elle réapparaîtrait au prochain
enregistrement.

CE QU'IL NE PORTE PAS NON PLUS, ET POURQUOI
---------------------------------------------
L'AXE DES RANGÉES. Il n'est jamais saisi : il est DÉRIVÉ du kit et de
l'azimut par ``core.calepinage.orientation.axe_rangee_impose``, seule source
de vérité du dépôt sur ce qui est constructible. Un gabarit qui le
transporterait pourrait imposer une combinaison inconstructible.

OÙ ÇA VIT
---------
Section ``gabarits_disposition`` de ``ParametresCalepinage`` (CAL45) : aucun
modèle, aucune migration. Ce module ne PERSISTE rien lui-même et n'écrit aucun
document : il normalise, extrait et applique. C'est
``services.parametres.enregistrer_parametres`` qui écrit, comme pour toutes
les autres sections.

COORDINATION (CAL201/CAL83) : la bibliothèque du module range ses presets,
kits et favoris dans ``services/bibliotheque.py``. Les GABARITS de disposition
vivent ici, dans leur propre section — deux tiroirs distincts, jamais deux
écritures de la même section.

ÉQUIVALENCE : une société sans gabarit garde ``gabarits_disposition: {}`` —
comportement d'aujourd'hui, strictement inchangé.
"""
from __future__ import annotations

from .parametres import ReglageInvalide

#: La section des réglages que ce module porte (CAL45).
SECTION = 'gabarits_disposition'

#: Les réglages de pose qu'un gabarit peut porter, avec leur libellé. Tuple
#: (pas un dict) : c'est un contrat figé, pas une table qu'on mute.
REGLAGES = (
    ('libelle', 'Libellé'),
    ('orientation', 'Orientation du module'),
    ('famille', 'Famille de table'),
    ('rives', 'Rives'),
    ('allee_m', 'Allée'),
    ('roofType', 'Type de toiture'),
    ('pitchDeg', 'Pente'),
    ('facingAzimuthDeg', 'Azimut de face'),
    ('facingManual', 'Azimut saisi à la main'),
    ('neededAuto', 'Dimensionnement automatique'),
    ('priorite', 'Priorité'),
    # Publiées par le contrat CAL45
    # (``contract_samples/parametres_calepinage.json``, gabarit
    # « portrait_2x10 ») : une maille de pose en rangées × colonnes. Reprises
    # TELLES QUELLES — renommer une clé du contrat le casserait.
    ('rangees', 'Rangées'),
    ('colonnes', 'Colonnes'),
    # CALX405 — le seuil de pente RELEVÉE sous lequel un pan reçoit la
    # proposition d'un châssis incliné, et l'inclinaison saisie à lui
    # appliquer. Ni l'un ni l'autre n'est calculé ici : ce module les
    # valide et les transporte, ``services/traduction.py`` (CAL78) les
    # CONSOMME pour publier la proposition et sa raison.
    ('chassis_sous_pente_deg', 'Seuil châssis incliné'),
    ('chassis_inclinaison_deg', 'Inclinaison du châssis'),
)

#: Les réglages qui sont des COMPTES entiers strictement positifs.
COMPTES = ('rangees', 'colonnes')

#: Les clés de la ZONE que le gabarit repose lui-même (contrat v2). Les
#: autres réglages (orientation, famille, rives, allée) ne sont pas des
#: champs du document : ils alimentent le traducteur (CAL78).
CLES_DE_ZONE = ('roofType', 'pitchDeg', 'facingAzimuthDeg', 'facingManual',
                'neededAuto')

#: Ce qu'un gabarit ne portera JAMAIS : de la géométrie. La liste nomme les
#: clés réelles du schéma v2 pour que le refus soit compréhensible.
CLES_DE_GEOMETRIE = ('vertices', 'obstacles', 'geometry', 'outline', 'pin',
                     'exclusionZones', 'measurements', 'environment',
                     'sommets', 'contour', 'panels')

#: Les orientations de module admises (vocabulaire du noyau, en minuscules).
ORIENTATIONS = ('portrait', 'paysage')

#: Les familles de table admises (vocabulaire du document v2 ``geometry``).
FAMILLES = ('south', 'eastwest')

#: Les types de toiture admis (contrat v2 ``zones[].roofType``).
TYPES_TOITURE = ('flat', 'pitched')

#: Les quatre rives NOMMÉES du noyau — jamais un « retrait » unique.
RIVES = ('laterale_m', 'extremite_m', 'acrotere_m', 'joint_m')

__all__ = [
    'SECTION', 'REGLAGES', 'CLES_DE_ZONE', 'CLES_DE_GEOMETRIE',
    'ORIENTATIONS', 'FAMILLES', 'TYPES_TOITURE', 'RIVES', 'COMPTES',
    'reglages_admis',
    'normaliser_section_gabarits_disposition', 'gabarit_depuis_zone',
    'appliquer_gabarit',
]


def reglages_admis():
    """Les clés admises d'un gabarit — jamais une liste recopiée à la main."""
    return tuple(cle for cle, _libelle in REGLAGES)


def _libelle(cle):
    for nom, libelle in REGLAGES:
        if nom == cle:
            return libelle
    return cle


def _refus(message, champ):
    return ReglageInvalide(message, champ=champ)


def _nombre(valeur, champ, libelle, *, positif=True):
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
        raise _refus(f"« {libelle} » doit être un nombre "
                     f"(reçu : {type(valeur).__name__}).", champ)
    if positif and float(valeur) < 0:
        raise _refus(f"« {libelle} » ne peut pas être négatif "
                     f"(reçu : {valeur}).", champ)
    return float(valeur)


def _choix(valeur, admis, champ, libelle):
    texte = str(valeur).strip().lower()
    if texte not in admis:
        raise _refus(
            f"« {libelle} » : valeur inconnue « {valeur} ». Valeurs "
            f"admises : {', '.join(admis)}.", champ)
    return texte


def _rives(valeur, champ):
    if not isinstance(valeur, dict):
        raise _refus(f"« Rives » doit être un objet "
                     f"(reçu : {type(valeur).__name__}).", champ)
    inconnues = [str(cle) for cle in valeur if str(cle) not in RIVES]
    if inconnues:
        raise _refus(
            f"Rive inconnue : « {', '.join(inconnues)} ». Rives admises : "
            f"{', '.join(RIVES)}.", f'{champ}.{inconnues[0]}')
    return {str(cle): _nombre(brut, f'{champ}.{cle}', f'Rive {cle}')
            for cle, brut in valeur.items()}


def _gabarit(cle, brut):
    """UN gabarit VALIDÉ — géométrie refusée, réglages inconnus refusés."""
    champ = f'{SECTION}.{cle}'
    if not isinstance(brut, dict):
        raise _refus(f"Le gabarit « {cle} » doit être un objet "
                     f"(reçu : {type(brut).__name__}).", champ)

    geometrie = [str(k) for k in brut if str(k) in CLES_DE_GEOMETRIE]
    if geometrie:
        raise _refus(
            f"Le gabarit « {cle} » transporte de la géométrie de toit "
            f"(« {', '.join(geometrie)} ») : un gabarit ne porte que des "
            "règles de pose, jamais la forme d'un autre toit.",
            f'{champ}.{geometrie[0]}')

    admis = reglages_admis()
    inconnues = [str(k) for k in brut if str(k) not in admis]
    if inconnues:
        raise _refus(
            f"Réglage inconnu dans le gabarit « {cle} » : "
            f"« {', '.join(inconnues)} ». Réglages admis : "
            f"{', '.join(admis)}.", f'{champ}.{inconnues[0]}')

    propre = {}
    for nom, valeur in brut.items():
        nom = str(nom)
        sous_champ = f'{champ}.{nom}'
        if nom == 'libelle':
            texte = str(valeur or '').strip()
            if texte:
                propre[nom] = texte
        elif nom == 'orientation':
            propre[nom] = _choix(valeur, ORIENTATIONS, sous_champ,
                                 _libelle(nom))
        elif nom == 'famille':
            propre[nom] = _choix(valeur, FAMILLES, sous_champ, _libelle(nom))
        elif nom == 'roofType':
            propre[nom] = _choix(valeur, TYPES_TOITURE, sous_champ,
                                 _libelle(nom))
        elif nom == 'rives':
            propre[nom] = _rives(valeur, sous_champ)
        elif nom in ('facingManual', 'neededAuto'):
            if not isinstance(valeur, bool):
                raise _refus(
                    f"« {_libelle(nom)} » est un oui/non "
                    f"(reçu : {type(valeur).__name__}).", sous_champ)
            propre[nom] = valeur
        elif nom == 'priorite':
            if isinstance(valeur, bool) or not isinstance(valeur, int):
                raise _refus(
                    "« Priorité » est un nombre entier "
                    f"(reçu : {type(valeur).__name__}).", sous_champ)
            propre[nom] = valeur
        elif nom in COMPTES:
            if isinstance(valeur, bool) or not isinstance(valeur, int) \
                    or valeur < 1:
                raise _refus(
                    f"« {_libelle(nom)} » est un compte entier d'au moins 1 "
                    f"(reçu : {valeur!r}).", sous_champ)
            propre[nom] = valeur
        elif nom == 'facingAzimuthDeg':
            azimut = _nombre(valeur, sous_champ, _libelle(nom), positif=False)
            if not (0.0 <= azimut <= 360.0):
                raise _refus(
                    "« Azimut de face » est un cap entre 0 et 360 degrés "
                    f"(reçu : {valeur}).", sous_champ)
            propre[nom] = azimut
        elif nom == 'pitchDeg':
            pente = _nombre(valeur, sous_champ, _libelle(nom))
            if pente >= 90.0:
                raise _refus(
                    "« Pente » est un angle strictement inférieur à 90 "
                    f"degrés (reçu : {valeur}).", sous_champ)
            propre[nom] = pente
        elif nom == 'chassis_sous_pente_deg':
            seuil = _nombre(valeur, sous_champ, _libelle(nom))
            if not (0.0 < seuil < 90.0):
                raise _refus(
                    "« Seuil châssis incliné » est un angle strictement "
                    f"entre 0 et 90 degrés (reçu : {valeur}).", sous_champ)
            propre[nom] = seuil
        elif nom == 'chassis_inclinaison_deg':
            inclinaison = _nombre(valeur, sous_champ, _libelle(nom))
            if inclinaison >= 90.0:
                raise _refus(
                    "« Inclinaison du châssis » est un angle strictement "
                    f"inférieur à 90 degrés (reçu : {valeur}).", sous_champ)
            propre[nom] = inclinaison
        else:
            propre[nom] = _nombre(valeur, sous_champ, _libelle(nom))

    # CALX405 — une inclinaison saisie sans son seuil ne dit à partir de
    # quelle pente l'appliquer : refusée en nommant la clé manquante,
    # jamais un seuil inventé.
    if 'chassis_inclinaison_deg' in propre \
            and 'chassis_sous_pente_deg' not in propre:
        raise _refus(
            "« Inclinaison du châssis » exige « Seuil châssis incliné » : "
            "saisissez d'abord « chassis_sous_pente_deg ».",
            f'{champ}.chassis_sous_pente_deg')
    return propre


def normaliser_section_gabarits_disposition(valeur):
    """La section ``gabarits_disposition`` VALIDÉE : ``{clé: gabarit}``.

    Returns:
        ``{}`` si la section est vide — ÉQUIVALENCE : une société sans gabarit
        se comporte exactement comme aujourd'hui.

    Raises:
        ReglageInvalide: géométrie de toit dans un gabarit, réglage inconnu,
            ou valeur hors domaine — le champ fautif est NOMMÉ.
    """
    if valeur is None:
        return {}
    if not isinstance(valeur, dict):
        raise _refus(f"La section « {SECTION} » doit être un objet "
                     f"(reçu : {type(valeur).__name__}).", SECTION)
    if not valeur:
        return {}
    return {str(cle): _gabarit(str(cle), brut)
            for cle, brut in valeur.items()}


def gabarit_depuis_zone(zone, *, reglages=None, libelle=''):
    """Les RÈGLES de pose d'une zone, prêtes à être enregistrées.

    Args:
        zone: la zone du document v2. Seules ses clés de RÈGLE sont lues ; sa
            géométrie est ignorée à la lecture (et refusée à l'écriture).
        reglages: les réglages qui ne vivent pas dans le document —
            ``orientation``, ``famille``, ``rives``, ``allee_m``,
            ``priorite``. Ce sont ceux que le traducteur (CAL78) consomme.
        libelle: le nom lisible du gabarit.

    Returns:
        Un gabarit NORMALISÉ (donc déjà validé). Une clé absente de la zone
        reste absente du gabarit : un gabarit ne contient que ce qui a été
        réellement réglé — jamais un défaut inventé qui s'imposerait ensuite
        à toutes les zones auxquelles on l'applique.
    """
    zone = zone if isinstance(zone, dict) else {}
    brut = {cle: zone[cle] for cle in CLES_DE_ZONE if cle in zone}
    for cle, valeur in (reglages or {}).items():
        if valeur is not None:
            brut[str(cle)] = valeur
    if libelle:
        brut['libelle'] = libelle
    return _gabarit(libelle or 'gabarit', brut)


def appliquer_gabarit(gabarit, zone=None):
    """``(zone réglée, règles moteur)`` — la géométrie de la zone est INTACTE.

    Args:
        gabarit: un gabarit normalisé (tel qu'il est stocké).
        zone: la zone à régler. ``None`` rend une zone neuve ne portant que
            les réglages (l'écran y posera son contour).

    Returns:
        ``(zone, regles)`` :

        * ``zone`` — une COPIE de la zone reçue, avec les seules clés que le
          contrat v2 définit déjà (``roofType``, ``pitchDeg``,
          ``facingAzimuthDeg``, ``facingManual``, ``neededAuto``). Son
          contour, ses obstacles et sa géométrie posée ne sont pas touchés :
          appliquer un gabarit ne redessine jamais un toit ;
        * ``regles`` — les réglages que le document ne porte pas
          (``orientation``, ``famille``, ``rives``, ``allee_m``,
          ``priorite``), à passer au traducteur CAL78.

    Un gabarit muet sur un réglage laisse la zone INCHANGÉE sur ce point :
    appliquer un gabarit partiel n'efface rien.
    """
    gabarit = gabarit or {}
    reglee = dict(zone or {})
    for cle in CLES_DE_ZONE:
        if cle in gabarit:
            reglee[cle] = gabarit[cle]
    regles = {cle: valeur for cle, valeur in gabarit.items()
              if cle not in CLES_DE_ZONE and cle != 'libelle'}
    return (reglee, regles)
