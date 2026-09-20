"""CAL78 — LE traducteur ``roof_layout`` v2 → entrée du moteur pur.

LE CONSTAT
----------
La porte HTTP du moteur existe (CAL22) et la bascule en tâche de fond aussi
(CAL23), mais RIEN ne savait transformer le document de l'atelier (contour,
pans, obstacles, zones, kit) en l'entrée que ``core.calepinage`` attend. Sans
ce traducteur, chaque appelant en réinventerait un — et deux traducteurs du
même document, c'est deux calepinages du même toit.

CE QU'IL FAIT, ET CE QU'IL NE REFAIT PAS
-----------------------------------------
* il PROJETTE une fois pour toutes : pans, obstacles et zones passent par la
  MÊME projection locale (``services.zones.projeteur_local``, celle de CAL237
  et CAL68) — deux projections différentes dans un même document poseraient
  les zones à côté des pans, de façon plausible et fausse ;
* il ne recopie AUCUNE forme : l'entrée est construite en objets du noyau
  (``SurfacePolygone``, ``Obstacle``, ``Zone``, ``Kit``, ``Parametres``) puis
  sérialisée par ``EntreeCalepinage.vers_dict()``. Le jour où le contrat
  moteur gagne un champ, ce traducteur le suit sans être retouché ;
* il réutilise CAL68 pour les zones (``zones_moteur_depuis_layout``) au lieu
  d'en écrire une seconde lecture ;
* il ne POSE rien et n'écrit rien : il rend un document et les objets que le
  moteur ne sait pas lire depuis un document (politique de pas, projection).

LE KIT : CHIFFRABLE OU REFUSÉ, JAMAIS DEVINÉ
---------------------------------------------
Le document d'atelier ne porte QUE ``panelWatt`` : les cotes du module sont,
côté site, une CONSTANTE de l'écran (``PANEL2_LONG_M`` / ``PANEL2_SHORT_M``
de ``apps/web/src/lib/roofPro2.ts``). Reprendre cette constante ici serait
exactement le repli interdit par CAL78 (« jamais un repli silencieux sur les
cotes d'un autre module ») : le client a peut-être acheté un autre panneau, et
personne ne verrait l'écart. Les cotes viennent donc, dans cet ordre :

1. le PRODUIT référencé, par ``apps.stock.selectors.dimensions_de_pose``
   (CAL119) — la fiche technique fait foi ;
2. des cotes EXPLICITEMENT transmises par l'appelant, ou portées par le
   document sous ``panelLengthM`` / ``panelWidthM`` (additif : aucun document
   existant n'en porte, aucun n'est cassé) ;
3. sinon REFUS, en nommant le champ manquant.

La PUISSANCE suit la même discipline : ``puissance_wc`` de la fiche, sinon
``panelWatt`` du document, sinon refus. Aucun ``KIT_VILLA_720`` par défaut.

LA LATITUDE — CE QUE CE TRADUCTEUR TRANSMET, ET CE QU'IL NE PEUT PAS
---------------------------------------------------------------------
``AntiOmbrage`` sait, depuis CAL167, calculer l'élévation solaire du LIEU au
lieu de la constante nationale de 21° — et ce changement est déjà journalisé
comme le MAJEUR ``2.0.0`` de ``core/calepinage/version.py`` (« un compte
publiable change à toiture identique dès que la latitude est déclarée »). Ce
traducteur DÉCLARE donc la latitude du site (celle de l'épingle, jamais une
ville devinée) dans la politique qu'il rend : c'est le comportement que la
version en vigueur décrit, aucun nouveau MAJEUR n'est dû, et AUCUN golden ne
bouge — l'adaptateur villa (``core/calepinage/adaptateurs/villa.py``) n'est
pas touché et continue de construire son ``AntiOmbrage()`` sans latitude.

LIMITE CONNUE, ÉCRITE PLUTÔT QUE TUE : le document d'échange du moteur
(``serialisation.py``) n'a AUCUN champ pour une politique de pas, et
``apps.ao.calepinage_service.calepiner`` appelle le moteur sans politique
(donc ``AlleeFixe(allee_m)``). La politique rendue ici n'est donc consommée
que par un appelant qui la passe lui-même au moteur ; tant que la chaîne HTTP
ne la transporte pas, le compte publié reste celui d'aujourd'hui.

UN SEUL AXE DE RANGÉE PAR DOCUMENT
-----------------------------------
Le repère du moteur a TOUJOURS ``x`` le long des rangées : la conversion
est/nord → ``(x, y)`` est celle de l'adaptateur villa (``_vers_repere``),
importée et non recopiée. Les zones et les obstacles sont GLOBAUX dans
l'entrée du moteur : si deux pans imposaient deux axes différents, la même
zone devrait exister dans deux repères à la fois. Ce document est donc REFUSÉ
en nommant le pan fautif, plutôt que de rendre une géométrie plausible et
fausse.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple

#: CAL72 — les deux vocabulaires de provenance du dépôt sont acceptés :
#: ``apps.ao.models.ObstacleAO`` dit MESURE / MESURE_DOUTEUX là où
#: ``core.calepinage.types.Provenance`` dit RELEVE / RELEVE_DOUTEUX. Ce sont
#: les MÊMES états ; refuser l'une des deux graphies ferait rougir un
#: producteur réel (c'est écrit noir sur blanc dans le contrat v2).
SYNONYMES_PROVENANCE = {
    'MESURE': 'RELEVE',
    'MESURE_DOUTEUX': 'RELEVE_DOUTEUX',
}

#: Types de l'atelier qui ont un ÉQUIVALENT EXACT dans l'énuméré du moteur.
#: Les autres restent ``NATURE_INCONNUE`` : inventer une correspondance
#: approximative ferait porter à l'obstacle le dégagement par défaut d'un
#: autre objet. Le dégagement, lui, est transmis explicitement.
TYPES_MOTEUR = {
    'cheminee': 'SOUCHE',
    'edicule': 'EDICULE',
    'antenne': 'ANTENNE',
}

__all__ = [
    'TraductionRefusee', 'Traduction', 'entree_depuis_layout',
    'SYNONYMES_PROVENANCE', 'TYPES_MOTEUR',
]


class TraductionRefusee(ValueError):
    """Refus métier, en français, avec le CHAMP fautif nommé.

    Un « document invalide » générique oblige l'utilisateur à deviner ce
    qu'il doit corriger : ``champ`` porte le chemin exact
    (``zones[0].vertices``, ``panelWatt``…).
    """

    def __init__(self, message, champ=''):
        super().__init__(message)
        self.champ = champ


@dataclass(frozen=True)
class Traduction:
    """Ce que le traducteur rend : le document, et ce qu'un document ne dit pas.

    * ``document`` — l'entrée du moteur, conforme à
      ``core/calepinage/schema.json`` ;
    * ``politique`` / ``politiques`` — la politique de pas du premier pan et
      celle de CHAQUE pan (un toit plat et un toit en pente ne se posent pas
      pareil) ; le document d'échange n'a aucun champ pour les porter ;
    * ``projection`` — ``(lon, lat) -> (x, y)`` du repère de travail, pour
      reprojeter les tables posées vers l'écran ;
    * ``latitude_deg`` — celle de l'épingle, ``None`` si le document n'en
      porte aucune (jamais une ville devinée) ;
    * ``engageable`` / ``motifs_non_engageable`` — le RÉGIME DE PREUVE des
      obstacles, remonté tel quel depuis ``core.calepinage.obstacles``.
    """

    document: dict
    politique: object = None
    politiques: Tuple[Tuple[str, object], ...] = ()
    projection: object = None
    latitude_deg: Optional[float] = None
    engageable: bool = True
    motifs_non_engageable: Tuple[str, ...] = ()
    kit: object = None
    axe_rangee: str = ''
    #: CAL71 — la phrase de règle du RETRAIT de rive appliqué. Celle de chaque
    #: obstacle voyage sur l'obstacle lui-même (``regle_appliquee``).
    regle_retrait: str = ''
    avertissements: Tuple[str, ...] = field(default=())


# ------------------------------------------------------------------ lectures
def _document(roof_layout):
    if roof_layout is None or not isinstance(roof_layout, dict):
        raise TraductionRefusee(
            "La conception doit être un objet : reçu "
            f"{type(roof_layout).__name__}.", 'roof_layout')
    return roof_layout


def _nombre(valeur):
    """Le nombre, ou ``None`` — un booléen n'est JAMAIS un nombre ici."""
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
        return None
    return float(valeur)


def _pans(roof_layout):
    pans = roof_layout.get('zones')
    if not isinstance(pans, list) or not pans:
        raise TraductionRefusee(
            "Cette conception ne porte aucun pan de toiture : dessinez au "
            "moins une zone avant de calculer.", 'zones')
    propres = []
    for rang, pan in enumerate(pans):
        if not isinstance(pan, dict):
            raise TraductionRefusee(
                f"Le pan n° {rang + 1} doit être un objet (reçu : "
                f"{type(pan).__name__}).", f'zones[{rang}]')
        sommets = _sommets_lnglat(pan.get('vertices'), f'zones[{rang}]',
                                  rang)
        propres.append((rang, pan, sommets))
    return propres


def _sommets_lnglat(points, champ, rang):
    if not isinstance(points, list) or len(points) < 3:
        raise TraductionRefusee(
            f"Le pan n° {rang + 1} n'a pas de contour fermé : « vertices » "
            "attend au moins 3 sommets.", f'{champ}.vertices')
    propres = []
    for point in points:
        if (not isinstance(point, (list, tuple)) or len(point) < 2
                or _nombre(point[0]) is None or _nombre(point[1]) is None):
            raise TraductionRefusee(
                f"Sommet illisible dans le pan n° {rang + 1} "
                f"(reçu : {point!r}).", f'{champ}.vertices')
        propres.append((float(point[0]), float(point[1])))
    return propres


def _origine(roof_layout, pans):
    """L'ancre de la projection : l'épingle, sinon le barycentre du 1er pan.

    Jamais une ville, jamais un centre de pays : sans géométrie exploitable,
    le document est REFUSÉ.
    """
    epingle = roof_layout.get('pin')
    if isinstance(epingle, dict):
        lat = _nombre(epingle.get('lat'))
        lon = _nombre(epingle.get('lng'))
        if lat is not None and lon is not None:
            return (lon, lat)
    sommets = pans[0][2]
    return (sum(p[0] for p in sommets) / len(sommets),
            sum(p[1] for p in sommets) / len(sommets))


# --------------------------------------------------------------------- kit
def _cotes_du_produit(produit):
    """``(long_m, court_m, puissance_wc)`` d'un produit — via le SÉLECTEUR.

    ``apps.stock.selectors.dimensions_de_pose`` est le seul chemin autorisé
    (frontière inter-apps) et il rend un dict dont une clé non saisie est
    ABSENTE, jamais ``None`` : on ne peut donc pas confondre « non saisi » et
    « zéro ».
    """
    from apps.stock.selectors import dimensions_de_pose

    cotes = dimensions_de_pose(produit) or {}
    longueur = cotes.get('longueur_mm')
    largeur = cotes.get('largeur_mm')
    manquants = [nom for nom, valeur in (('longueur_mm', longueur),
                                         ('largeur_mm', largeur))
                 if _nombre(valeur) is None or float(valeur) <= 0]
    if manquants:
        raise TraductionRefusee(
            "La fiche technique du panneau retenu ne porte pas ses cotes de "
            f"pose : renseignez « {' » et « '.join(manquants)} » sur la "
            "fiche du produit avant de calepiner.",
            f'produit.fiche_technique.{manquants[0]}')
    return (float(longueur) / 1000.0, float(largeur) / 1000.0,
            _nombre(cotes.get('puissance_wc')))


def _kit(roof_layout, produit, cotes_module, inclinaison_deg, orientation,
         modules_par_table, faitage_m, code):
    """Le kit CHIFFRABLE, ou un refus qui NOMME le champ manquant."""
    from core.calepinage.types import Kit, OrientationModule

    puissance = None
    if produit is not None:
        longueur_m, largeur_m, puissance = _cotes_du_produit(produit)
    elif cotes_module:
        longueur_m = _nombre(cotes_module[0])
        largeur_m = _nombre(cotes_module[1])
    else:
        longueur_m = _nombre(roof_layout.get('panelLengthM'))
        largeur_m = _nombre(roof_layout.get('panelWidthM'))

    if longueur_m is None or largeur_m is None \
            or longueur_m <= 0 or largeur_m <= 0:
        raise TraductionRefusee(
            "Ce document ne dit pas quelles sont les COTES du panneau : "
            "rattachez le produit du catalogue (sa fiche technique porte "
            "« longueur_mm » et « largeur_mm ») ou transmettez "
            "« panelLengthM » et « panelWidthM ». Les cotes d'un autre "
            "module ne sont jamais reprises à la place.",
            'panelLengthM')

    if puissance is None:
        puissance = _nombre(roof_layout.get('panelWatt'))
    if puissance is None or puissance <= 0:
        raise TraductionRefusee(
            "Ce document ne dit pas quelle est la PUISSANCE du panneau : "
            "renseignez « panelWatt » (ou « pmax_wc » sur la fiche technique "
            "du produit) avant de calepiner.", 'panelWatt')

    long_m, court_m = max(longueur_m, largeur_m), min(longueur_m, largeur_m)
    return Kit(
        code=code,
        libelle="Panneau %.0f Wc (%.3f × %.3f m) — cotes du document"
                % (puissance, long_m, court_m),
        module_long_m=long_m, module_court_m=court_m,
        puissance_module_wc=float(puissance),
        inclinaison_deg=float(inclinaison_deg),
        orientation=(orientation if isinstance(orientation,
                                               OrientationModule)
                     else OrientationModule(str(orientation))),
        modules_par_table=int(modules_par_table),
        faitage_m=float(faitage_m))


# --------------------------------------------------------------- obstacles
def _provenance(brut, champ):
    from core.calepinage.types import Provenance

    valeur = brut.get('provenance')
    if valeur is None:
        # Contrat v2 : provenance absente = comportement d'aujourd'hui, aucun
        # motif de non-engageabilité tiré d'elle.
        return Provenance.RELEVE
    nom = str(valeur).strip().upper()
    nom = SYNONYMES_PROVENANCE.get(nom, nom)
    try:
        return Provenance(nom)
    except ValueError:
        raise TraductionRefusee(
            f"Provenance d'obstacle inconnue : « {valeur} ». Valeurs "
            "admises : " + ', '.join(p.value for p in Provenance)
            + ', MESURE, MESURE_DOUTEUX.', f'{champ}.provenance')


def _degagement(brut, provenance, section):
    """``(dégagement, phrase)`` — la règle société, RELEVÉE au plancher de provenance.

    CAL71 : la valeur et sa justification viennent de ``services/degagements``
    — réglage de la société s'il existe, sinon la valeur de l'atelier annoncée
    « non sourcée ». Ce module ne porte plus aucune table de dégagement : deux
    tables seraient deux règles.

    Le dégagement transmis est EXPLICITE (le moteur le traite comme une
    surcharge), donc il court-circuiterait le plancher que la provenance
    impose (``core/calepinage/obstacles.py``). On prend donc le MAXIMUM des
    deux : un obstacle venu du plan ne se retrouve jamais moins dégagé parce
    que l'atelier, lui, ne connaît pas la provenance.
    """
    from core.calepinage.obstacles import degagement_par_provenance

    from .degagements import degagement_du_type

    regle, phrase = degagement_du_type(brut.get('type'), section)
    plancher = degagement_par_provenance(provenance)
    if plancher > regle:
        return (plancher,
                "provenance %s impose %.2f m, au-delà de la règle appliquée "
                "— %s" % (provenance.value, plancher, phrase))
    return (regle, phrase)


def _obstacles(pans, vers_repere, section=None):
    from core.calepinage.types import Obstacle, TypeObstacle

    sortie = []
    for rang, pan, _sommets in pans:
        bruts = pan.get('obstacles')
        if bruts is None:
            continue
        champ_pan = f'zones[{rang}].obstacles'
        if not isinstance(bruts, list):
            raise TraductionRefusee(
                f"« {champ_pan} » doit être une liste (reçu : "
                f"{type(bruts).__name__}).", champ_pan)
        for i, brut in enumerate(bruts):
            champ = f'{champ_pan}[{i}]'
            if not isinstance(brut, dict):
                raise TraductionRefusee(
                    f"L'obstacle n° {i + 1} doit être un objet (reçu : "
                    f"{type(brut).__name__}).", champ)
            lon = _nombre(brut.get('centerLng'))
            lat = _nombre(brut.get('centerLat'))
            if lon is None or lat is None:
                raise TraductionRefusee(
                    f"L'obstacle « {brut.get('id') or i + 1} » n'a pas de "
                    "centre : « centerLng » et « centerLat » sont attendus.",
                    f'{champ}.centerLng')
            # ``lengthM`` est une étendue NORD-SUD et ``widthM`` une étendue
            # EST-OUEST (contrat v2) : sur des rangées nord-sud, les deux
            # échangent leur rôle EN MÊME TEMPS que les coordonnées.
            est_ouest = _nombre(brut.get('widthM'))
            nord_sud = _nombre(brut.get('lengthM'))
            if est_ouest is None or nord_sud is None \
                    or est_ouest <= 0 or nord_sud <= 0:
                raise TraductionRefusee(
                    f"L'obstacle « {brut.get('id') or i + 1} » n'a pas de "
                    "dimensions exploitables : « lengthM » (nord-sud) et "
                    "« widthM » (est-ouest) sont attendus, strictement "
                    "positifs.", f'{champ}.lengthM')
            provenance = _provenance(brut, champ)
            degagement, regle = _degagement(brut, provenance, section)
            x, y = vers_repere((lon, lat))
            demi_x, demi_y = vers_repere.demi(est_ouest / 2.0,
                                              nord_sud / 2.0)
            type_moteur = TYPES_MOTEUR.get(str(brut.get('type') or ''),
                                           'NATURE_INCONNUE')
            sortie.append(Obstacle(
                repere=str(brut.get('id') or f'OBS{len(sortie) + 1}'),
                x0=x - demi_x, x1=x + demi_x,
                y0=y - demi_y, y1=y + demi_y,
                type_obstacle=TypeObstacle(type_moteur),
                provenance=provenance,
                degagement_m=degagement,
                hauteur_m=_nombre(brut.get('heightM')),
                regle_appliquee=regle))
    return tuple(sortie)


# ------------------------------------------------------------------- repère
class _VersRepere:
    """``(lon, lat) -> (x, y)`` : projection locale PUIS axe des rangées.

    L'axe est appliqué par ``core.calepinage.adaptateurs.villa._vers_repere``
    — la SEULE implémentation du dépôt. La recopier ici ferait deux repères
    du même toit le jour où l'une des deux change.
    """

    def __init__(self, projeter, axe):
        self._projeter = projeter
        self._axe = axe

    def __call__(self, point):
        from core.calepinage.adaptateurs.villa import _vers_repere

        est, nord = self._projeter(point)
        return _vers_repere(est, nord, self._axe)

    def demi(self, demi_est, demi_nord):
        """Les DEMI-dimensions, transposées comme les coordonnées."""
        from core.calepinage.adaptateurs.villa import _vers_repere

        return _vers_repere(demi_est, demi_nord, self._axe)


# -------------------------------------------------------------------- pans
def _pente_et_azimut(pan):
    """``(pente, azimut, plat)`` du pan — les défauts du document, pas les nôtres.

    ``roofType`` / ``pitchDeg`` / ``facingAzimuthDeg`` sont OPTIONNELS depuis
    F2 (« une zone posée par le SERVEUR les OMET délibérément : personne n'a
    mesuré ce toit »). Absents, on lit ce que le contrat dit : toiture PLATE,
    pente 0, plein sud — exactement ce qu'appliquent les deux lecteurs
    existants (``newAreaRecord()``), jamais une valeur inventée ici.
    """
    pente = _nombre(pan.get('pitchDeg'))
    azimut = _nombre(pan.get('facingAzimuthDeg'))
    genre = pan.get('roofType')
    plat = (genre != 'pitched') if genre is not None else (
        pente is None or pente < 5.0)
    return (pente or 0.0, 180.0 if azimut is None else azimut, plat)


def _axe_unique(pans, kit):
    """L'axe des rangées du document — REFUS si les pans n'en imposent qu'un.

    Les zones et les obstacles de l'entrée moteur sont GLOBAUX : un document
    à deux axes devrait les exprimer dans deux repères à la fois.
    """
    from core.calepinage.orientation import axe_rangee_impose

    axes = []
    for rang, pan, _sommets in pans:
        _pente, azimut, _plat = _pente_et_azimut(pan)
        axes.append((rang, axe_rangee_impose(kit, azimut)))
    premier = axes[0][1]
    for rang, axe in axes:
        if axe is not premier:
            raise TraductionRefusee(
                "Les pans de cette conception imposent deux axes de rangée "
                f"différents ({premier.value} et {axe.value}) : le pan n° "
                f"{rang + 1} ne peut pas partager les mêmes zones et les "
                "mêmes obstacles que le premier. Calepinez-les séparément.",
                f'zones[{rang}].facingAzimuthDeg')
    return premier


def _politique(plat, pente, latitude_deg):
    """Toit PLAT → anti-ombrage ; toit en PENTE → pose affleurante.

    Même règle que l'adaptateur villa (``politique_villa``), à une différence
    ASSUMÉE et documentée en tête de module : la latitude du site est
    DÉCLARÉE quand le document la porte.
    """
    from core.calepinage.politique_pas import Affleurant, AntiOmbrage

    if plat and pente < 5.0:
        return AntiOmbrage(latitude_deg=latitude_deg)
    return Affleurant()


# ------------------------------------------------------------------- entrée
def entree_depuis_layout(roof_layout, *, produit=None, cotes_module=None,
                         parametres=None, repere='', inclinaison_deg=10.0,
                         orientation='PORTRAIT', modules_par_table=1,
                         faitage_m=0.0, code_kit='PANNEAU',
                         allee_m=None, retrait_m=None, pas_recherche_m=0.01):
    """Traduit un document ``roof_layout`` v2 en entrée du moteur pur.

    Args:
        roof_layout: le document d'atelier (schéma v2, CAL232).
        produit: le produit du catalogue qui porte les cotes de pose. Lu par
            ``apps.stock.selectors.dimensions_de_pose`` — jamais par
            ``apps.stock.models``.
        cotes_module: ``(longueur_m, largeur_m)`` transmises explicitement,
            quand aucun produit n'est rattaché.
        parametres: les sections de réglages de la société
            (``selectors.parametres_de_societe``). Seules les valeurs
            RÉELLEMENT saisies sont lues ; une section absente laisse le
            comportement d'aujourd'hui.
        repere: le repère du chantier dans le document rendu.
        allee_m / retrait_m: forcent l'allée et le retrait de rive. Par
            défaut : ceux de la société, sinon ceux de l'atelier.

    Returns:
        Une ``Traduction`` (document + politique + projection + régime de
        preuve).

    Raises:
        TraductionRefusee: document illisible, kit non chiffrable, deux axes
            de rangée, zone ou obstacle invalide — le champ fautif est NOMMÉ.
    """
    from core.calepinage.obstacles import appliquer_regles, engageable
    from core.calepinage.serialisation import EntreeCalepinage, _zone_depuis
    from core.calepinage.surfaces.polygone import SurfacePolygone
    from core.calepinage.types import Parametres, Rives

    from .zones import ZoneRefusee, projeteur_local, zones_moteur_depuis_layout

    roof_layout = _document(roof_layout)
    pans = _pans(roof_layout)
    kit = _kit(roof_layout, produit, cotes_module, inclinaison_deg,
               orientation, modules_par_table, faitage_m, code_kit)
    axe = _axe_unique(pans, kit)

    origine = _origine(roof_layout, pans)
    vers_repere = _VersRepere(projeteur_local(origine), axe)

    from .degagements import (
        SECTION as SECTION_DEGAGEMENTS, allee_technique, retrait_perimetre,
    )

    sections = parametres or {}
    degagements = sections.get(SECTION_DEGAGEMENTS) or {}
    # CAL71 — le retrait de rive de la société, sinon celui de l'atelier
    # annoncé « non sourcé ». La phrase de règle voyage avec l'entrée.
    retrait, regle_retrait = retrait_perimetre(degagements)
    force = _nombre(retrait_m) if retrait_m is not None else None
    if force is not None:
        retrait, regle_retrait = force, (
            "Retrait de rive : %.2f m (valeur transmise par l'appelant)"
            % (force,))
    allee = _nombre(allee_m) if allee_m is not None else None
    if allee is None:
        allee, _regle_allee = allee_technique(degagements)
    rives = Rives(laterale_m=retrait, extremite_m=retrait)

    surfaces = []
    politiques = []
    latitude = origine[1]
    for rang, pan, sommets in pans:
        pente, azimut, plat = _pente_et_azimut(pan)
        repere_pan = str(pan.get('id') or f'PAN{rang + 1}')
        surfaces.append(SurfacePolygone(
            repere=repere_pan,
            contour=tuple(vers_repere(p) for p in sommets),
            rives=rives, axe_rangee=axe, pente_deg=pente,
            azimut_deg=azimut))
        politiques.append((repere_pan, _politique(plat, pente, latitude)))

    try:
        zones = tuple(_zone_depuis(z) for z in zones_moteur_depuis_layout(
            roof_layout, projection=vers_repere))
    except ZoneRefusee as refus:
        # CAL68 a déjà écrit le refus en français et nommé son champ : le
        # retraduire ici produirait deux formulations de la même règle.
        raise TraductionRefusee(str(refus), refus.champ)

    obstacles = _obstacles(pans, vers_repere, degagements)
    parametres_moteur = Parametres(
        kits=(kit,), rives=rives, axe_rangee=axe,
        pas_recherche_m=pas_recherche_m,
        **({} if allee is None else {'allee_m': allee}))

    entree = EntreeCalepinage(
        repere=str(repere or roof_layout.get('activeAreaId') or 'CALEPINAGE'),
        surfaces=tuple(surfaces), kits=(kit,),
        parametres=parametres_moteur, obstacles=obstacles, zones=zones)

    ok, motifs = engageable(appliquer_regles(obstacles))
    return Traduction(
        document=entree.vers_dict(),
        politique=politiques[0][1] if politiques else None,
        politiques=tuple(politiques),
        projection=vers_repere,
        latitude_deg=latitude,
        engageable=ok,
        motifs_non_engageable=tuple(motifs),
        kit=kit,
        axe_rangee=axe.value,
        regle_retrait=regle_retrait)
