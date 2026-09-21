"""CAL131 — sections et chutes de tension sur les LONGUEURS DU PLAN.

LE DÉFAUT CORRIGÉ
-----------------
``core/electrique/cables.py`` sait déjà tout faire (``ampacite``,
``chute_tension_pct``, ``proposer_section`` avec le critère dimensionnant) —
mais personne ne lui donne une longueur RÉELLE : le devis emploie des forfaits
(``ac_cable_length_m=15.0`` par défaut dans ``apps/ventes/solar_design.py``,
métrés par paliers côté écran). Une section calculée sur un forfait est une
section qu'on ne peut pas défendre.

CE QUE CE SERVICE FAIT
----------------------
Il DÉDUIT les longueurs de liaison du calepinage :

* la course DC dans le pan est mesurée sur les CENTRES DE MODULES POSÉS
  (``geometry.panels[].cx/cy``, mètres dans le repère du pan) jusqu'au point
  de collecte du pan — point SAISI par le poseur (le plan ne dit pas où on a
  mis le coffret) ;
* la descente et la liaison coffret → onduleur → TGBT sont SAISIES : aucun
  plan ne les porte.

La longueur retenue est celle de la course la PLUS LONGUE (le câble doit
tenir la pire liaison, pas la moyenne), et chaque câble publié porte sa
longueur ET SON ORIGINE (plan, saisie, ou les deux).

DEUX REFUS EXPLICITES
---------------------
1. **Longueur inconnue ⇒ AUCUNE section publiée.** Pas de forfait de secours :
   un métré manquant se corrige en 30 secondes, une section fausse se
   découvre sur le chantier.
2. **Norme non sélectionnée ⇒ calcul OMIS** (règle D5, CAL130). Les barèmes
   d'ampacité et les chutes cibles du noyau citent NF C 15-100 / UTE
   C 15-712-1 ; les appliquer à une société qui n'a choisi aucune norme
   reviendrait à imprimer une référence française sur un chantier qui ne l'a
   pas retenue.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple

__all__ = [
    'Longueur', 'longueur_dc', 'longueur_ac', 'cables_du_calepinage',
    'MOTIF_LE_LONG_DE_LA_RANGEE', 'MOTIF_ALLER_RETOUR', 'MOTIFS_PARCOURS',
    'MotifDeParcoursInvalide', 'course_de_chaine',  # CALX218
]

ORIGINE_PLAN = 'plan'
ORIGINE_SAISIE = 'saisie'
ORIGINE_MIXTE = 'plan et saisie'

# ═══════════════════════════════════════════════════════════════════════════
# CALX218 — LE MOTIF DE PARCOURS D'UNE CHAÎNE, ET LA LONGUEUR QUI EN DÉCOULE
# ═══════════════════════════════════════════════════════════════════════════
#
# ``_course_du_pan`` ne mesure que la distance EUCLIDIENNE du module le plus
# éloigné au point de collecte : le trajet réel LE LONG des modules de la
# chaîne n'est jamais parcouru, et le câble de chaîne est donc
# systématiquement SOUS-MÉTRÉ. Parité : HelioScope offre un routage
# « along- vs. up/down-array » (https://help-center.helioscope.com/hc/en-us/
# articles/4419953067411-4-Electrical-Design).
#
# LE MOTIF EST UNE SAISIE, JAMAIS UNE DEVINETTE. Deux valeurs, et il n'y en a
# pas de troisième ; sans saisie, le comportement d'aujourd'hui est conservé
# et NOMMÉ comme tel dans le détail de la longueur (D-CALX 7 : on ne fabrique
# pas un trajet que personne n'a décidé).

#: La liaison suit les modules de la chaîne d'un bout à l'autre, puis rejoint
#: le point de collecte depuis le DERNIER module (aller simple).
MOTIF_LE_LONG_DE_LA_RANGEE = 'le_long_de_la_rangee'

#: La liaison suit les modules, rejoint le point de collecte, et y REVIENT
#: par le premier module : la chaîne se referme là où elle a commencé.
MOTIF_ALLER_RETOUR = 'aller_retour'

#: L'énumération FERMÉE des motifs admis. Un motif hors de cette liste est
#: REFUSÉ en nommant le champ — jamais interprété au mieux.
MOTIFS_PARCOURS = (MOTIF_LE_LONG_DE_LA_RANGEE, MOTIF_ALLER_RETOUR)

#: Le détail publié quand AUCUN motif n'est saisi : il DIT que le trajet réel
#: n'a pas été parcouru, au lieu de laisser croire à une mesure de chemin.
DETAIL_SANS_MOTIF = (
    "aucun motif de parcours saisi : distance du module le plus éloigné au "
    "point de collecte — le trajet le long des modules de la chaîne n'est "
    "pas parcouru")

#: Le détail publié pour chaque motif retenu — c'est LUI que le résultat
#: affiche à côté de la longueur (``longueur_detail``).
DETAIL_PAR_MOTIF = {
    MOTIF_LE_LONG_DE_LA_RANGEE: (
        "motif de parcours saisi « le long de la rangée » : somme des "
        "segments entre centres de modules consécutifs, puis liaison du "
        "dernier module au point de collecte"),
    MOTIF_ALLER_RETOUR: (
        "motif de parcours saisi « aller-retour » : somme des segments entre "
        "centres de modules consécutifs, liaison du dernier module au point "
        "de collecte, et retour au point de collecte par le premier module"),
}


class MotifDeParcoursInvalide(ValueError):
    """Motif de parcours hors énumération — champ fautif NOMMÉ."""

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ


@dataclass(frozen=True)
class Longueur:
    """Une longueur de liaison AVEC son origine — jamais un nombre nu."""

    valeur_m: float
    origine: str
    detail: str
    composantes: Tuple[Tuple[str, float, str], ...] = ()

    def en_dict(self):
        return {
            'valeur_m': round(self.valeur_m, 2),
            'origine': self.origine,
            'detail': self.detail,
            'composantes': [{'poste': poste, 'valeur_m': round(valeur, 2),
                             'origine': origine}
                            for poste, valeur, origine in self.composantes],
        }


def _nombre(valeur):
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None


def _centres(panneaux):
    """Les centres EXPLOITABLES, dans l'ordre du plan — jamais réordonnés.

    L'ordre du document EST l'ordre de pose : le réordonner ici inventerait
    un trajet que personne n'a dessiné.
    """
    retenus = []
    for panneau in panneaux or ():
        if not isinstance(panneau, dict):
            continue
        x = _nombre(panneau.get('cx'))
        y = _nombre(panneau.get('cy'))
        if x is not None and y is not None:
            retenus.append((x, y))
    return retenus


def _modules_de_la_chaine(chaine, centres):
    """Les centres que CETTE chaîne traverse, dans l'ordre.

    ``chaine`` peut DÉCLARER ses modules (``modules``: rangs 1-based dans le
    plan du pan, ou index) ; sans déclaration, la chaîne est la série des
    modules posés du pan, dans l'ordre du plan.
    """
    declares = (chaine or {}).get('modules') if isinstance(chaine, dict) \
        else getattr(chaine, 'modules', None)
    if not isinstance(declares, (list, tuple)) or not declares:
        return list(centres)
    retenus = []
    for rang in declares:
        index = _nombre(rang)
        if index is None:
            continue
        index = int(index)
        # Les rangs du plan se comptent à partir de 1 ; un 0 explicite est
        # lu comme un index, jamais « tous les modules ».
        index = index - 1 if index >= 1 else index
        if 0 <= index < len(centres):
            retenus.append(centres[index])
    return retenus


def course_de_chaine(chaine, panneaux, motif=None, *, point_collecte=None):
    """CALX218 — la course d'UNE chaîne, selon son MOTIF DE PARCOURS.

    Args:
        chaine: la chaîne mesurée — elle NOMME le résultat et, quand elle
            déclare ses ``modules``, les SÉLECTIONNE parmi ``panneaux``.
            ``None`` = la série des modules posés du pan, dans l'ordre du plan.
        panneaux: les centres de modules du plan (``geometry.panels``).
        motif: ``le_long_de_la_rangee``, ``aller_retour``, ou ``None`` —
            aucun motif saisi, la distance d'aujourd'hui (module le plus
            éloigné) est conservée et le détail le DIT.
        point_collecte: le point de collecte SAISI du pan (``{cx, cy}``).

    Returns:
        ``Longueur`` (origine ``plan`` : tous les centres sont mesurés sur le
        plan — le motif est une RÈGLE de parcours, pas une source de mesure ;
        c'est le ``detail`` qui le cite), ou ``None`` quand le plan ne porte
        aucun centre exploitable ou que le point de collecte n'est pas saisi.
        Aucune longueur partielle n'est jamais rendue.

    Raises:
        MotifDeParcoursInvalide: motif hors de l'énumération fermée.
    """
    if motif not in (None, '') and motif not in MOTIFS_PARCOURS:
        raise MotifDeParcoursInvalide(
            "Motif de parcours inconnu « %s » : les seuls motifs admis sont "
            "%s." % (motif, ', '.join('« %s »' % m for m in MOTIFS_PARCOURS)),
            champ='motif_parcours')

    centres = _centres(panneaux)
    cible_x = _nombre((point_collecte or {}).get('cx'))
    cible_y = _nombre((point_collecte or {}).get('cy'))
    if not centres or cible_x is None or cible_y is None:
        return None
    modules = _modules_de_la_chaine(chaine, centres)
    if not modules:
        return None

    nom = ''
    if isinstance(chaine, dict):
        nom = str(chaine.get('repere') or '')
    elif chaine is not None:
        nom = str(getattr(chaine, 'repere', '') or '')
    poste = ("parcours de la chaîne « %s »" % nom) if nom \
        else 'parcours des modules du pan'

    if not motif:
        valeur = max(math.hypot(x - cible_x, y - cible_y)
                     for x, y in modules)
        return Longueur(valeur_m=valeur, origine=ORIGINE_PLAN,
                        detail=DETAIL_SANS_MOTIF,
                        composantes=(('module le plus éloigné du point de '
                                      'collecte', valeur, ORIGINE_PLAN),))

    le_long = sum(math.hypot(aval[0] - amont[0], aval[1] - amont[1])
                  for amont, aval in zip(modules, modules[1:]))
    depuis_dernier = math.hypot(modules[-1][0] - cible_x,
                                modules[-1][1] - cible_y)
    composantes = [(poste, le_long, ORIGINE_PLAN),
                   ('dernier module → point de collecte', depuis_dernier,
                    ORIGINE_PLAN)]
    if motif == MOTIF_ALLER_RETOUR:
        composantes.append(
            ('retour au point de collecte par le premier module',
             math.hypot(modules[0][0] - cible_x, modules[0][1] - cible_y),
             ORIGINE_PLAN))
    return Longueur(
        valeur_m=sum(valeur for _poste, valeur, _origine in composantes),
        origine=ORIGINE_PLAN, detail=DETAIL_PAR_MOTIF[motif],
        composantes=tuple(composantes))


def _course_du_pan(pan_document, point_collecte, motif=None):
    """La course du pan (m) et son détail, ou ``(None, '')``.

    Les centres sont ceux réellement posés (``geometry.panels``), dans le
    repère du pan : c'est la seule mesure que le plan porte vraiment. Le
    parcours, lui, suit le MOTIF saisi (CALX218) — à défaut, la distance du
    module le plus éloigné, comme avant.
    """
    geometrie = (pan_document or {}).get('geometry')
    if not isinstance(geometrie, dict):
        return (None, '')
    course = course_de_chaine(None, geometrie.get('panels'), motif,
                              point_collecte=point_collecte)
    return (None, '') if course is None else (course.valeur_m, course.detail)


def longueur_dc(layout, cheminement):
    """``(Longueur | None, manques)`` — la liaison DC la plus longue.

    Trois composantes : la course dans le pan (PLAN), la descente (SAISIE) et
    la liaison coffret → onduleur (SAISIE). Une composante manquante rend
    ``None`` et NOMME ce qui manque : aucune section ne sera publiée.

    CALX218 — la course d'un pan suit son MOTIF DE PARCOURS quand il est
    saisi (``cheminement.pans.<pan>.motif_parcours``) ; le détail publié cite
    alors le motif retenu. Sans saisie, la course est celle d'aujourd'hui, et
    le détail DIT que le trajet le long des modules n'a pas été parcouru.
    """
    cheminement = cheminement or {}
    manques = []
    zones = (layout or {}).get('zones')
    zones = zones if isinstance(zones, (list, tuple)) else []
    points = (cheminement.get('pans') or {}) if isinstance(
        cheminement.get('pans'), dict) else {}

    courses = []
    for rang, zone in enumerate(zones, start=1):
        if not isinstance(zone, dict):
            continue
        libelle = str(zone.get('label') or zone.get('id') or 'PAN-%d' % rang)
        geometrie = zone.get('geometry')
        if not isinstance(geometrie, dict) or not geometrie.get('panels'):
            continue
        saisie_du_pan = points.get(libelle) or {}
        try:
            course, detail = _course_du_pan(
                zone, saisie_du_pan.get('point_collecte'),
                saisie_du_pan.get('motif_parcours'))
        except MotifDeParcoursInvalide as refus:
            manques.append("pan « %s » : %s" % (libelle, refus))
            continue
        if course is None:
            manques.append(
                "pan « %s » : point de collecte non saisi (ou centres de "
                "modules absents du plan) — la course DC de ce pan n'est pas "
                "mesurable" % libelle)
            continue
        courses.append((libelle, course, detail))

    if not courses:
        if not manques:
            manques.append("aucun module posé avec des centres exploitables : "
                           "la course DC n'est pas mesurable")
        return (None, tuple(manques))

    descente = _nombre(cheminement.get('descente_m'))
    vers_onduleur = _nombre(cheminement.get('coffret_vers_onduleur_m'))
    if descente is None:
        manques.append("descente verticale non saisie (m) — elle ne se lit "
                       "sur aucun plan")
    if vers_onduleur is None:
        manques.append("liaison coffret → onduleur non saisie (m)")
    if manques:
        return (None, tuple(manques))

    pan_pire, course, detail_course = max(
        courses, key=lambda triplet: triplet[1])
    total = course + descente + vers_onduleur
    detail = ("course la plus longue mesurée sur le plan (pan « %s » — %s) "
              "+ descente et liaison coffret → onduleur saisies"
              % (pan_pire, detail_course))
    return (Longueur(
        valeur_m=total, origine=ORIGINE_MIXTE, detail=detail,
        composantes=(
            ('course dans le pan « %s »' % pan_pire, course, ORIGINE_PLAN),
            ('descente verticale', descente, ORIGINE_SAISIE),
            ('coffret → onduleur', vers_onduleur, ORIGINE_SAISIE),
        )), ())


def longueur_ac(cheminement):
    """``(Longueur | None, manques)`` — la liaison onduleur → TGBT, SAISIE.

    Aucun plan de toiture ne porte le chemin jusqu'au tableau général : cette
    longueur est saisie, et son absence empêche toute section AC (jamais un
    forfait de 15 m).
    """
    valeur = _nombre((cheminement or {}).get('onduleur_vers_tgbt_m'))
    if valeur is None:
        return (None, ("liaison onduleur → TGBT non saisie (m) : aucun plan "
                       "ne la porte, et aucun forfait n'est appliqué à sa "
                       "place",))
    return (Longueur(valeur_m=valeur, origine=ORIGINE_SAISIE,
                     detail='liaison onduleur → TGBT saisie',
                     composantes=(('onduleur → TGBT', valeur,
                                   ORIGINE_SAISIE),)), ())


def _cable_publie(cable, longueur):
    """Un câble du noyau, publié AVEC l'origine de sa longueur."""
    return {
        'repere': cable.repere,
        'designation': cable.designation,
        'section_mm2': cable.section_mm2,
        'nb_conducteurs': cable.nb_conducteurs,
        'longueur_m': round(cable.longueur_m, 2),
        'longueur_origine': longueur.origine,
        'longueur_detail': longueur.detail,
        'ib_a': round(cable.ib_a, 2),
        'in_a': cable.in_a,
        'iz_a': cable.iz_a,
        'chute_tension_pct': round(cable.chute_tension_pct, 3),
        'chute_cible_pct': cable.chute_cible_pct,
        'chute_max_pct': cable.chute_max_pct,
        'critere_dimensionnant': cable.critere_dimensionnant,
        'conforme': cable.conforme,
        'regle_source': cable.regle_source,
    }


def _longueur_de_branche(branche, cable):
    """La longueur d'une branche AC, AVEC son origine (CALX209/CALX210).

    Une branche de micro-onduleurs n'est tracée sur aucun plan de toiture :
    sa longueur est SAISIE sur la branche (``longueur_m``), exactement comme
    la liaison onduleur → TGBT. Le document peut néanmoins déclarer une autre
    origine (``longueur_origine``, vocabulaire de CALX202) — elle est alors
    reprise telle quelle plutôt que réécrite.
    """
    branche = branche if isinstance(branche, dict) else {}
    origine = str(branche.get('longueur_origine') or '').strip() \
        or ORIGINE_SAISIE
    nom = str(branche.get('repere') or cable.repere)
    return Longueur(
        valeur_m=float(cable.longueur_m or 0.0), origine=origine,
        detail="longueur de la branche « %s » (« longueur_m ») : aucun plan "
               "de toiture ne porte le chemin du départ AC" % nom,
        composantes=((('branche « %s »' % nom),
                      float(cable.longueur_m or 0.0), origine),))


def cables_du_calepinage(conception, *, cheminement=None, norme=None,
                         layout=None, branches_ac=None):
    """CAL131 — les câbles DC et AC dimensionnés sur les longueurs du plan.

    Args:
        conception: la ``Conception`` de CAL124 (chaînes déjà calculées).
        cheminement: le cheminement SAISI (points de collecte par pan,
            descente, coffret → onduleur, onduleur → TGBT).
        norme: le verdict de ``services.norme.norme_applicable`` — sans norme
            applicable, le calcul est OMIS (règle D5).
        layout: le document de conception (à défaut, celui de la conception).
        branches_ac: les branches AC de micro-onduleurs publiées par CALX209.
            Fournies, les ``W2.1 … W2.N`` de CALX210 REMPLACENT la liaison AC
            unique : une installation à micro-onduleurs n'a pas un onduleur au
            bout d'un câble, elle a N départs protégés — publier en plus un
            ``W2`` forfaitaire ferait un câble qui n'existe pas. Absentes (tout
            onduleur de chaîne), la sortie est celle d'aujourd'hui, champ pour
            champ.

    Returns:
        ``{cables, longueurs, omissions, noyau}`` — ``omissions`` dit, en
        français, POURQUOI un câble n'a pas de section. Aucune valeur par
        défaut n'est jamais substituée à une longueur manquante.

        ``noyau`` porte les TROIS objets purs qui ont produit les lignes
        ci-dessus (``{entree, protections, cables}`` de ``core.electrique``),
        ou ``None`` quand rien n'a pu être dimensionné. Il n'est jamais
        sérialisé : il existe pour que le BORDEREAU (``core.electrique.
        nomenclature``) soit bâti sur EXACTEMENT le même calcul que les
        câbles publiés, au lieu d'un second dimensionnement qui en divergerait.
    """
    import dataclasses

    from core.electrique.cables import dimensionner_cables
    from core.electrique.protections import concevoir_protections

    from .chaines import evaluer_onduleurs

    omissions = []
    if norme is not None and not norme.get('applicable', False):
        return {'cables': [], 'longueurs': {'dc': None, 'ac': None},
                'omissions': [norme.get('motif') or
                              "aucune norme électrique sélectionnée : "
                              "sections et chutes de tension OMISES"],
                'noyau': None}
    if conception.fiche_incomplete or conception.resultat is None \
            or not conception.chaines:
        return {'cables': [], 'longueurs': {'dc': None, 'ac': None},
                'omissions': ["aucune chaîne calculée : il n'y a pas de "
                              "liaison à dimensionner"],
                'noyau': None}

    document = layout if layout is not None else _document(conception)
    dc, manques_dc = longueur_dc(document, cheminement)
    omissions.extend(manques_dc)
    if branches_ac:
        # Régime micro-onduleurs : il n'y a pas de liaison « onduleur → TGBT »
        # à mesurer, donc rien à réclamer — chaque branche porte SA longueur,
        # et c'est elle que ``dimensionner_branches_ac`` nomme quand elle
        # manque (CALX210).
        ac, manques_ac = None, ()
    else:
        ac, manques_ac = longueur_ac(cheminement)
    omissions.extend(manques_ac)

    entree = dataclasses.replace(
        conception.entree,
        dc_m=dc.valeur_m if dc is not None else 0.0,
        ac_m=ac.valeur_m if ac is not None else 0.0)
    evaluation = evaluer_onduleurs(conception)
    protections = concevoir_protections(entree, conception.resultat,
                                        evaluation)
    branches = tuple(branches_ac or ())
    resultat = dimensionner_cables(entree, conception.resultat, protections,
                                   branches_ac=branches or None)
    # ``dimensionner_branches_ac`` numérote ``W2.<rang>`` sur le RANG de la
    # branche reçue (une branche non dimensionnable n'émet aucun câble, mais
    # ne décale pas les suivantes) : la correspondance est donc l'index.
    par_repere = {'W2.%d' % (rang + 1): branche
                  for rang, branche in enumerate(branches)}

    publies = []
    for cable in resultat.cables:
        if cable.repere == 'W1':
            if dc is None:
                continue
            publies.append(_cable_publie(cable, dc))
        elif cable.repere == 'W2':
            if ac is None:
                continue
            publies.append(_cable_publie(cable, ac))
        elif str(cable.repere).startswith('W2.'):
            publies.append(_cable_publie(
                cable, _longueur_de_branche(par_repere.get(cable.repere),
                                            cable)))
    omissions.extend(resultat.bloquants)
    omissions.extend(resultat.alertes)

    return {
        'cables': publies,
        'longueurs': {'dc': dc.en_dict() if dc is not None else None,
                      # En régime micro-onduleurs, la liaison AC unique
                      # n'existe pas : publier la longueur saisie « onduleur →
                      # TGBT » à côté de N départs ferait croire à un câble de
                      # plus. La clé reste PRÉSENTE, à ``null``.
                      'ac': (None if branches
                             else (ac.en_dict() if ac is not None else None))},
        'omissions': omissions,
        'noyau': {'entree': entree, 'protections': protections,
                  'cables': resultat},
    }


def _document(conception):
    """Reconstitue un document minimal quand l'appelant n'en passe pas.

    Le service préfère TOUJOURS le document réel (les centres de modules n'y
    sont pas devinables) ; ce repli ne sert qu'à ne pas planter.
    """
    return {'zones': []}
