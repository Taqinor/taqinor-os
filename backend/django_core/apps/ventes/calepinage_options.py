"""CORRECTION #8 (ordre fondateur, 26/08/2026) — le calepinage PAR OPTION.

« add per option drawing of the pv ». La page client montre trois tailles
explorables (:mod:`apps.ventes.offres_tailles`) et, en dessous, UNE vue de
détail vivante qui bascule sur l'option choisie. Ce module fabrique la moitié
« dessin » de cette vue : le calepinage de CHAQUE option, dans ses deux
variantes ``sans``/``avec``.

CE QUE CE MODULE NE FAIT PAS, ET C'EST L'ESSENTIEL
---------------------------------------------------
* **Il n'invente aucun toit.** Chaque dessin DÉRIVE du calepinage RÉEL stocké
  sur le devis : même polygone, même orientation, même trame de rangées, mêmes
  obstacles. Moins de panneaux ⇒ on en RETIRE par la fin des rangées ; plus de
  panneaux ⇒ on PROLONGE la trame À L'INTÉRIEUR du polygone réel. Un panneau
  hors du contour ne peut pas exister ici : les QUATRE COINS d'une empreinte
  CONSERVATRICE doivent tomber dans le polygone, au-delà du retrait de rive et
  hors du dégagement de tout obstacle — donc un emplacement douteux est
  REFUSÉ, jamais accordé.

  CETTE EMPREINTE N'EST CONSERVATRICE QUE SUR UNE VRAIE LATTICE, et c'est
  pourquoi :meth:`_Trame.trame_reguliere` existe : sur un pavage MIXTE (PV62 —
  pose choisie rangée par rangée), le pas retenu serait le plus petit des
  deux et l'empreinte deviendrait plus PETITE que le panneau dessiné. La
  dérivation refuse alors de prolonger, plutôt que de valider une contenance
  qui ne couvre pas le rendu.
* **Il n'invente aucun format de dessin.** Le ``layout`` d'une option a
  EXACTEMENT la forme que la page lit déjà pour la clé racine ``roof_layout``
  (``apps/web/src/lib/proposition.ts`` ``parseRoofLayout`` →
  ``scripts/roofPro11/viewerFullModel.ts`` ``buildViewerFullPlan``) : la
  visionneuse 3D existante est rejouée telle quelle sur l'objet de l'option.
  Le backend ne rend AUCUN SVG de calepinage — il n'en a jamais rendu : le
  calepinage client EST la visionneuse WebGL, et ``roof_image_url`` reste la
  photo d'étude.
* **Il ne calcule rien de commercial.** Les comptes de panneaux lui sont
  DONNÉS (le bloc ``offres_tailles`` déjà dérivé par la vue) : ni composition,
  ni balayage, ni conception électrique ne sont rejoués. C'est de la géométrie
  plane sur quelques dizaines de points, sur un endpoint public non caché.
* **Il n'écrit rien.** Lecture pure (règle #4).

LA GÉOMÉTRIE, EN UN PARAGRAPHE
-------------------------------
Les centres de panneaux stockés (``zone.geometry.panels[].{cx,cy}``) sont des
mètres ENU (x = Est, y = Nord) dans le repère ``geometry.origin`` ([lng, lat]).
On les projette dans le repère de POSE : ``u`` le long des rangées, ``v`` dans
le sens de la visée — reconstruit depuis ``geometry.azimuthDeg`` avec LA MÊME
convention que le calepineur (``apps/web/src/lib/roofPro2.ts`` :
``f = [sin az, cos az]``, ``s = f``, ``u = [-f1, f0]``). Une rangée est un
paquet de panneaux de même ``v`` ; l'ordre canonique est zone (ordre stocké) →
rangée (``v`` croissant) → panneau (``u`` croissant). Le contour de la zone est
reprojeté en ENU par la MÊME formule que la page
(``viewerFullModel.ringENUFromVertices``), de sorte que le test « dans le
polygone » du serveur et le dessin du navigateur parlent du même toit.

Contrat partagé : ``apps/ventes/contract_samples/calepinage_options.json``.
"""
from __future__ import annotations

import logging
import math

logger = logging.getLogger(__name__)

_DEG2RAD = math.pi / 180.0
#: Rayon WGS84 (m) — MÊME constante que ``lib/roofPro2.ts`` et
#: ``viewerFullModel.ringENUFromVertices`` : la projection ENU du serveur doit
#: être celle du navigateur au mètre près, sinon le test de contenance ne parle
#: plus du polygone que le client voit.
_RAYON_WGS84 = 6378137.0
_DEG2M = _DEG2RAD * _RAYON_WGS84

#: Deux panneaux dont la coordonnée « dans le sens de la visée » diffère de
#: moins que ça sont sur la MÊME rangée. Par construction les ``v`` d'une
#: rangée sont IDENTIQUES (grille régulière) — cette tolérance n'absorbe que
#: l'erreur flottante et les micro-écarts d'une pose retouchée. Elle reste très
#: en dessous du plus petit pas de rangée physiquement possible (le petit côté
#: d'un panneau incliné, ~0,65 m au pire), donc elle ne peut pas fusionner deux
#: rangées voisines.
_TOLERANCE_RANGEE_M = 0.30

#: Écart minimal (m) pour qu'une différence de position COMPTE comme un pas.
#: MÊME seuil que le client (``lib/proposition.ts`` ``inferPanelPose`` :
#: ``if (gap > 1e-3 …)``) : en dessous, ce sont deux panneaux d'une MÊME
#: colonne (rangées empilées, ou les deux versants d'un chevron Est-Ouest) —
#: pas une mesure de pas. Le 1e-6 d'origine laissait le bruit flottant
#: (``sin(180°) ≈ 1e-16``) se faire passer pour un pas de grille.
_EPS_PAS_M = 1e-3

#: Tolérance (m) du critère « cet écart est un multiple entier du pas ».
#: Généreuse VOLONTAIREMENT : elle doit absorber le bruit d'une pose retouchée
#: sans jamais absorber la différence entre un pas portrait (~1,32 m) et un pas
#: paysage (~2,40 m) — c'est cette différence-là que la garde PV62 doit voir.
_TOLERANCE_LATTICE_M = 0.05

#: Retrait de rive (m) exigé des quatre coins d'un emplacement AJOUTÉ. C'est le
#: retrait PAR DÉFAUT du calepineur — ``lib/roofPro2.ts`` ``PERIMETER_SETBACK_M``,
#: le ``fallbackM`` de ``resolveSetbacks`` et le repli
#: ``estimatorBrainV2`` ``opts.setbackM ?? PERIMETER_SETBACK_M`` (miroir
#: visionneuse : ``VIEWER_SETBACK_M``).
#:
#: LIMITE CONNUE, DITE HONNÊTEMENT (PV63) : le calepineur accepte désormais des
#: retraits PAR CÔTÉ (``resolveSetbacks`` → ``{lateralM, extremityM,
#: parapetM}``), et ces trois valeurs NE SONT PAS SÉRIALISÉES dans le layout
#: (``prefill.ts`` ne les émet pas). Un dessin dérivé prolonge donc toujours au
#: retrait par défaut de 0,5 m. Conséquence bornée et connue : sur un toit
#: réglé à un retrait PLUS GRAND, une rangée ajoutée peut s'approcher du bord
#: plus près que le commercial ne l'aurait fait — jamais hors du polygone. Le
#: jour où les retraits par côté voyageront dans le layout, ils se lisent ici.
_RETRAIT_RIVE_M = 0.5

#: PV61 — dégagement (m) autour d'un obstacle, PAR TYPE. Table recopiée de
#: ``apps/web/src/scripts/roofPro11/types.ts`` ``CLEARANCE_BY_TYPE`` : les
#: obstacles HAUTS ou salissants (cheminée, chien-assis, édicule) demandent
#: 0,50 m — suie, ombre portée, accès d'entretien ; les autres gardent le
#: dégagement de base.
_DEGAGEMENT_DEFAUT = 0.3          # estimatorBrainV2 OBSTACLE_CLEARANCE_M
_DEGAGEMENTS = {
    'cheminee': 0.5,
    'chien_assis': 0.5,
    'edicule': 0.5,
    'ventilation': _DEGAGEMENT_DEFAUT,
    'antenne': _DEGAGEMENT_DEFAUT,
    'autre': _DEGAGEMENT_DEFAUT,
}

#: Bornes de travail — un endpoint public non caché ne fait pas de géométrie
#: non bornée. Au-delà, on plafonne (et on le DIT via ``plafonne``).
_MAX_COLONNES_AJOUTEES = 6
_MAX_RANGEES_AJOUTEES = 6
_MAX_CANDIDATS = 600
#: Même plafond dur que la visionneuse (``VIEWER_MAX_PANELS``) : au-delà elle
#: ne dessinerait pas plus, inutile de transporter davantage.
_MAX_PANNEAUX_DESSINES = 600

#: Les clés de ``zone.geometry`` recopiées telles quelles sur un dessin dérivé.
#: ``count`` et ``panels`` sont réestampillés ; ``kwc`` est VOLONTAIREMENT
#: absent (c'est la puissance du calepinage RÉEL — la coller sur le dessin
#: d'une autre taille serait un chiffre faux, et la page n'en a pas besoin :
#: la carte porte déjà les kWc de SA taille).
_GEO_RECOPIEES = ('azimuthDeg', 'tiltDeg', 'family', 'flush', 'origin')

#: Les SEULES clés de zone recopiées sur un dessin dérivé — une WHITELIST, au
#: même sens strict que ``public_views._ZONE_KEYS`` : ce qui n'est pas nommé
#: ici n'existe pas en sortie. ``neededPanels`` en est volontairement absente
#: (c'est la cible dimensionnée par l'étude du DEVIS, elle ne décrit pas la
#: taille explorée) et ``geometry`` aussi (elle est reconstruite).
_ZONE_RECOPIEES = ('id', 'label', 'vertices', 'roofType',
                   'pitchDeg', 'facingAzimuthDeg')

#: Les SEULES clés d'un OBSTACLE recopiées. La liste d'obstacles était le
#: dernier endroit recopié EN BLOC : une sonde d'injection y a fait voyager un
#: ``prix_achat`` niché dans un obstacle. Ce sont exactement les champs que la
#: page lit (``proposition.parseRoofLayout``) plus ``type`` (PV61, le
#: dégagement) — rien d'autre n'a de raison d'exister sur un dessin.
_OBSTACLE_RECOPIEES = ('id', 'centerLng', 'centerLat', 'lengthM', 'widthM',
                       'type')


# ════════════════════════════════════════════════════════════════════════════
# GÉOMÉTRIE PLANE — pure, sans Django, testable seule
# ════════════════════════════════════════════════════════════════════════════

def _fini(valeur):
    """``float`` fini, ou ``None`` (un booléen n'est JAMAIS une coordonnée)."""
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
        return None
    nombre = float(valeur)
    if nombre != nombre or nombre in (float('inf'), float('-inf')):
        return None
    return nombre


def _multiple(ecart, pas):
    """``ecart`` est-il un MULTIPLE ENTIER de ``pas`` (à la tolérance près) ?

    Le critère de régularité d'une lattice. La tolérance est celle de la
    géométrie du toit, pas celle du flottant : un pavage mixte se trahit par
    des écarts de l'ordre du décimètre, jamais du millimètre.
    """
    if pas is None or pas <= _EPS_PAS_M:
        return False
    reste = abs(ecart) / pas
    return abs(reste - round(reste)) * pas <= _TOLERANCE_LATTICE_M


def axes_de_pose(azimut_deg):
    """``(u, s)`` — l'axe LONG des rangées et l'axe de la visée.

    MÊME convention que le calepineur : ``f = [sin az, cos az]`` est la visée,
    les rangées s'empilent vers elle (``s = f``) et s'étirent perpendiculaire
    (``u = [-f1, f0]``).
    """
    az = float(azimut_deg) * _DEG2RAD
    f = (math.sin(az), math.cos(az))
    return (-f[1], f[0]), f


def _vers_uv(cx, cy, u, s):
    return (cx * u[0] + cy * u[1], cx * s[0] + cy * s[1])


def _vers_enu(uu, vv, u, s):
    return (uu * u[0] + vv * s[0], uu * u[1] + vv * s[1])


def anneau_enu(vertices, origine):
    """Le contour [[lng,lat],…] reprojeté en mètres ENU autour de ``origine``.

    Formule IDENTIQUE à ``viewerFullModel.ringENUFromVertices`` — c'est ce qui
    garantit que « dans le polygone » veut dire la même chose ici et à l'écran.
    """
    olng = _fini((origine or [None, None])[0])
    olat = _fini((origine or [None, None])[1])
    if olng is None or olat is None:
        return []
    cos_lat = math.cos(olat * _DEG2RAD)
    anneau = []
    for sommet in vertices or []:
        if not isinstance(sommet, (list, tuple)) or len(sommet) < 2:
            continue
        lng = _fini(sommet[0])
        lat = _fini(sommet[1])
        if lng is None or lat is None:
            continue
        anneau.append(((lng - olng) * _DEG2M * cos_lat,
                       (lat - olat) * _DEG2M))
    return anneau


def _dans_polygone(point, anneau):
    """Lancer de rayon — ``True`` si le point est STRICTEMENT dans l'anneau."""
    px, py = point
    dedans = False
    n = len(anneau)
    for i in range(n):
        ax, ay = anneau[i]
        bx, by = anneau[(i + 1) % n]
        if (ay > py) != (by > py):
            t = (py - ay) / (by - ay) if by != ay else 0.0
            if px < ax + t * (bx - ax):
                dedans = not dedans
    return dedans


def _distance_bord(point, anneau):
    """Distance (m) du point au bord le plus proche de l'anneau."""
    px, py = point
    meilleure = float('inf')
    n = len(anneau)
    for i in range(n):
        ax, ay = anneau[i]
        bx, by = anneau[(i + 1) % n]
        dx, dy = bx - ax, by - ay
        norme = dx * dx + dy * dy
        if norme <= 0:
            distance = math.hypot(px - ax, py - ay)
        else:
            t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / norme))
            distance = math.hypot(px - (ax + t * dx), py - (ay + t * dy))
        meilleure = min(meilleure, distance)
    return meilleure


def obstacles_enu(obstacles, origine):
    """Les obstacles en boîtes ENU ``(xmin, ymin, xmax, ymax)``, DÉGAGEMENT INCLUS.

    ``lengthM`` EST L'ÉTENDUE NORD-SUD ET ``widthM`` L'ÉTENDUE EST-OUEST — pas
    l'inverse. La source de vérité est ``apps/web/src/lib/obstacles.ts``
    (``obstacleRing`` : ``dLat = lengthM/2``, ``dLng = widthM/2 / cosLat``),
    et le type le documente noir sur blanc (« Étendue nord-sud (m) » /
    « Étendue est-ouest (m) »). Les intervertir faisait pivoter la zone
    d'exclusion de 90° : sur une cheminée 1 m × 6 m, la boîte protégeait une
    bande de toit VIDE et laissait poser un panneau SUR la souche. Une boîte
    carrée ne peut pas révéler l'erreur — c'est le test non carré qui l'arme.

    PV61 — LE DÉGAGEMENT FAIT PARTIE DE LA BOÎTE. Le calepineur n'exige pas
    seulement « hors du rectangle » : il refuse tout coin à moins de
    ``clearance`` du bord (``estimatorBrainV2`` : ``pointInPolygon(c, o) ||
    distToBoundary(c, o) <= cl``), et ce dégagement est PROPRE AU TYPE
    (``CLEARANCE_BY_TYPE``). On gonfle donc chaque boîte de son dégagement ici,
    une fois : le test d'emplacement n'a plus qu'à ne pas la toucher.
    """
    olng = _fini((origine or [None, None])[0])
    olat = _fini((origine or [None, None])[1])
    if olng is None or olat is None:
        return []
    cos_lat = math.cos(olat * _DEG2RAD)
    boites = []
    for obstacle in obstacles or []:
        if not isinstance(obstacle, dict):
            continue
        lng = _fini(obstacle.get('centerLng'))
        lat = _fini(obstacle.get('centerLat'))
        nord_sud = _fini(obstacle.get('lengthM'))
        est_ouest = _fini(obstacle.get('widthM'))
        if None in (lng, lat, nord_sud, est_ouest):
            continue
        if nord_sud <= 0 or est_ouest <= 0:
            continue
        degagement = _DEGAGEMENTS.get(obstacle.get('type'),
                                      _DEGAGEMENT_DEFAUT)
        cx = (lng - olng) * _DEG2M * cos_lat
        cy = (lat - olat) * _DEG2M
        demi_x = est_ouest / 2.0 + degagement       # Est-Ouest = widthM
        demi_y = nord_sud / 2.0 + degagement        # Nord-Sud  = lengthM
        boites.append((cx - demi_x, cy - demi_y, cx + demi_x, cy + demi_y))
    return boites


# ════════════════════════════════════════════════════════════════════════════
# LA TRAME RÉELLE D'UNE ZONE
# ════════════════════════════════════════════════════════════════════════════

class _Trame:
    """La pose RÉELLE d'une zone, lue en rangées.

    ``rangees`` : liste ``[(v, [(u, panneau), …]), …]`` triée ``v`` croissant,
    chaque rangée triée ``u`` croissant.

    ``panneau`` est RECONSTRUIT champ par champ (``cx``, ``cy``, et ``face``
    dans son énumération fermée) au lieu d'être recopié par référence. Les
    coordonnées sont reprises TELLES QUELLES — un panneau conservé garde sa
    position au bit près — mais rien d'autre ne traverse : c'est la même
    défense en profondeur que ``_safe_zone_geometry`` (des échantillons de
    layout portent des ``prix_achat``/``marge`` nichés sur chaque panneau), et
    elle vaut ici même si un appelant se trompait un jour de source et
    passait le blob BRUT au lieu de sa version assainie.
    """

    #: Les seules faces existantes — même énumération fermée que la whitelist
    #: publique (``public_views._FACES_CONNUES``).
    FACES = ('E', 'W')

    def __init__(self, index, zone, geometrie, libre=False):
        self.index = index
        self.zone = zone
        self.geometrie = geometrie
        self.libre = bool(libre)
        self.u, self.s = axes_de_pose(geometrie.get('azimuthDeg') or 0.0)
        self.rangees = self._lire_rangees(geometrie.get('panels') or [])
        self.pas_colonne = self._pas_colonne()
        self.pas_rangee = self._pas_rangee()
        self.anneau = anneau_enu(zone.get('vertices'),
                                 geometrie.get('origin'))
        self.obstacles = obstacles_enu(zone.get('obstacles'),
                                       geometrie.get('origin'))

    # ── lecture ─────────────────────────────────────────────────────────────
    def _lire_rangees(self, panneaux):
        cellules = []
        for panneau in panneaux:
            if not isinstance(panneau, dict):
                continue
            cx = _fini(panneau.get('cx'))
            cy = _fini(panneau.get('cy'))
            if cx is None or cy is None:
                continue
            pose = {'cx': panneau['cx'], 'cy': panneau['cy']}
            if panneau.get('face') in self.FACES:
                pose['face'] = panneau['face']
            uu, vv = _vers_uv(cx, cy, self.u, self.s)
            cellules.append((vv, uu, pose))
        if not cellules:
            return []
        cellules.sort(key=lambda c: (c[0], c[1]))
        rangees, courante, v_courant = [], [], None
        for vv, uu, panneau in cellules:
            if v_courant is None or abs(vv - v_courant) > _TOLERANCE_RANGEE_M:
                if courante:
                    rangees.append((v_courant, courante))
                courante, v_courant = [], vv
            courante.append((uu, panneau))
        if courante:
            rangees.append((v_courant, courante))
        return rangees

    def _pas_colonne(self):
        """Le pas de grille RÉELLEMENT observé le long des rangées.

        Le MINIMUM des écarts positifs : un écart plus grand est un TROU (une
        cellule que le commercial a retirée), pas un pas de grille.
        """
        pas = None
        for _v, cellules in self.rangees:
            for i in range(1, len(cellules)):
                ecart = cellules[i][0] - cellules[i - 1][0]
                if ecart > _EPS_PAS_M and (pas is None or ecart < pas):
                    pas = ecart
        return pas

    def _pas_rangee(self):
        pas = None
        for i in range(1, len(self.rangees)):
            ecart = self.rangees[i][0] - self.rangees[i - 1][0]
            if ecart > _EPS_PAS_M and (pas is None or ecart < pas):
                pas = ecart
        return pas

    # ── ordre canonique ─────────────────────────────────────────────────────
    def panneaux_ordonnes(self):
        """Les panneaux posés, dans l'ordre canonique (v croissant, u croissant)."""
        return [panneau
                for _v, cellules in self.rangees
                for _u, panneau in cellules]

    @property
    def nb_panneaux(self):
        return sum(len(cellules) for _v, cellules in self.rangees)

    # ── extension ───────────────────────────────────────────────────────────
    def trame_reguliere(self):
        """La pose tient-elle VRAIMENT sur UNE lattice à pas unique ?

        PV62 — LE PAVAGE PEUT ÊTRE MIXTE : le calepineur choisit la pose
        (portrait / paysage) RANGÉE PAR RANGÉE (``ctx.sel.orient === 'mixed'``,
        un choix atteignable d'un clic), et les rangées ont alors des pas
        DIFFÉRENTS. Or ``_safe_zone_geometry`` ne publie PAS la pose par
        panneau (``orient``) : depuis la donnée assainie, un pavage mixte
        ressemble à un pavage uniforme.

        Sans cette garde, ``pas_colonne`` valait le MINIMUM des deux pas — donc
        le pas PORTRAIT — et l'empreinte de validation devenait PLUS PETITE que
        le panneau réellement dessiné sur les rangées paysage : la preuve de
        contenance ne couvrait plus le rendu (jusqu'à ~3 cm de coin hors
        polygone, et des panneaux qui s'interpénètrent d'un mètre à l'écran).

        La garde est arithmétique et n'invente rien : sur une VRAIE lattice,
        chaque écart dans une rangée et chaque écart entre rangées est un
        MULTIPLE ENTIER du pas. Dès qu'un écart ne l'est pas, on refuse de
        prolonger — la taille plafonne, ce qui est le pire honnête.
        """
        if self.pas_colonne is None or self.pas_rangee is None:
            return False
        for _v, cellules in self.rangees:
            for i in range(1, len(cellules)):
                ecart = cellules[i][0] - cellules[i - 1][0]
                if not _multiple(ecart, self.pas_colonne):
                    return False
        for i in range(1, len(self.rangees)):
            ecart = self.rangees[i][0] - self.rangees[i - 1][0]
            if not _multiple(ecart, self.pas_rangee):
                return False
        return True

    def extensible(self):
        """Peut-on PROLONGER cette zone sans deviner ?

        Il faut les DEUX pas (colonne et rangée) — sans le pas de rangée, la
        profondeur occupée par un panneau est inconnue, donc on ne peut pas
        PROUVER qu'un ajout tient — ET une trame réellement régulière (voir
        :meth:`trame_reguliere`, PV62). Une zone à une seule rangée, une pose
        faite À LA MAIN (``mode == 'free'``) ou un pavage mixte ne sont jamais
        prolongés : le dessin plafonne, et il le DIT.
        """
        return (not self.libre and bool(self.rangees)
                and self.trame_reguliere())

    def _emplacement_libre(self, uu, vv):
        """Les quatre coins d'une empreinte CONSERVATRICE tiennent-ils ?

        L'empreinte vaut ``pas_colonne`` × ``pas_rangee``. Sur la lattice
        UNIQUE que :meth:`trame_reguliere` vient de prouver, elle est plus
        grande que le panneau réel (le pas de colonne inclut le jeu entre
        panneaux ; le pas de rangée inclut l'ombre portée sur toit plat). Un
        emplacement accepté ici l'aurait donc été par le calepineur ; un
        emplacement refusé peut être un refus prudent — c'est le sens voulu.
        """
        du = self.pas_colonne / 2.0
        dv = self.pas_rangee / 2.0
        coins = [_vers_enu(uu + su * du, vv + sv * dv, self.u, self.s)
                 for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        for coin in coins:
            if not _dans_polygone(coin, self.anneau):
                return False
            if _distance_bord(coin, self.anneau) < _RETRAIT_RIVE_M:
                return False
        if self.obstacles:
            # Les boîtes portent DÉJÀ leur dégagement PV61 (voir
            # ``obstacles_enu``) : toucher l'une d'elles, c'est violer le
            # dégagement, pas seulement mordre la souche.
            xs = [c[0] for c in coins]
            ys = [c[1] for c in coins]
            xmin, xmax, ymin, ymax = min(xs), max(xs), min(ys), max(ys)
            for oxmin, oymin, oxmax, oymax in self.obstacles:
                if (xmin < oxmax and xmax > oxmin
                        and ymin < oymax and ymax > oymin):
                    return False
        return True

    def candidats(self, maximum):
        """Au plus ``maximum`` emplacements SUPPLÉMENTAIRES retenus, dans l'ordre.

        L'ordre est déterministe et raconte la même histoire qu'un poseur :
        1. on finit les rangées existantes (par la fin, ``u`` croissant),
        2. puis on les prolonge par le début,
        3. puis on ajoute des rangées entières au-delà de la dernière,
        4. puis avant la première.

        Les TROUS INTÉRIEURS ne sont JAMAIS rebouchés : un emplacement vide du
        calepinage réel (la cheminée contournée à la main) reste vide dans tous
        les dessins dérivés — c'est le toit du client, pas un re-pavage.

        ``maximum`` borne le TRAVAIL, pas seulement la sortie : on s'arrête dès
        qu'on a de quoi servir la taille demandée (endpoint non caché).
        """
        if maximum <= 0 or not self.extensible():
            return []
        retenus, essais = [], 0
        for uu, vv in self._positions_candidates():
            essais += 1
            if essais > _MAX_CANDIDATS:
                break
            if self._emplacement_libre(uu, vv):
                enu = _vers_enu(uu, vv, self.u, self.s)
                retenus.append({'cx': round(enu[0], 3),
                                'cy': round(enu[1], 3)})
                if len(retenus) >= maximum:
                    break
        return retenus

    def _positions_candidates(self):
        pas_u = self.pas_colonne
        pas_v = self.pas_rangee
        # 1 & 2 — prolongement des rangées existantes.
        for v, cellules in self.rangees:
            u_max = cellules[-1][0]
            for k in range(1, _MAX_COLONNES_AJOUTEES + 1):
                yield (u_max + k * pas_u, v)
        for v, cellules in self.rangees:
            u_min = cellules[0][0]
            for k in range(1, _MAX_COLONNES_AJOUTEES + 1):
                yield (u_min - k * pas_u, v)
        # 3 & 4 — nouvelles rangées, calquées sur la rangée la PLUS LARGE (la
        # trame réelle, jamais une trame inventée).
        modele = max(self.rangees, key=lambda r: len(r[1]))[1]
        colonnes = [u for u, _p in modele]
        v_haut = self.rangees[-1][0]
        v_bas = self.rangees[0][0]
        for k in range(1, _MAX_RANGEES_AJOUTEES + 1):
            for uu in colonnes:
                yield (uu, v_haut + k * pas_v)
        for k in range(1, _MAX_RANGEES_AJOUTEES + 1):
            for uu in colonnes:
                yield (uu, v_bas - k * pas_v)


# ════════════════════════════════════════════════════════════════════════════
# LE DESSIN D'UNE TAILLE
# ════════════════════════════════════════════════════════════════════════════

def _modes_libres(devis):
    """``(identifiants libres, rangs libres)`` — les zones posées À LA MAIN.

    ``geometry.mode == 'free'`` (PV30) n'est PAS republié par la whitelist
    publique : on va donc le chercher sur le blob stocké, et lui seul.

    LE RANG BRUT N'EST PAS LE RANG PUBLIÉ, et c'est ce qui rendait cette
    protection inopérante. ``_safe_roof_layout`` SAUTE les entrées qui ne sont
    pas des dicts ; un blob portant une entrée parasite avant une zone libre
    décalait donc tous les rangs d'un cran, la zone libre héritait du drapeau
    de sa voisine, et une pose faite à la main se faisait prolonger sur une
    lattice qu'elle n'a jamais eue.

    D'où DEUX clés, dans cet ordre : l'``id`` de zone (stable, présent sur
    toute zone sérialisée par le builder) et, en repli pour les blobs anciens
    sans ``id``, un rang calculé avec EXACTEMENT le même filtre que
    ``_safe_roof_layout`` (dicts seulement) — donc aligné sur la liste publiée.

    Une lecture ratée vaut « pas libre » — au pire on refuse d'étendre une zone
    qu'on aurait pu étendre, jamais l'inverse.
    """
    identifiants, rangs = set(), set()
    layout = getattr(devis, 'roof_layout', None)
    if not isinstance(layout, dict):
        return identifiants, rangs
    rang = 0
    for zone in layout.get('zones') or []:
        if not isinstance(zone, dict):
            # MÊME saut que ``_safe_roof_layout`` : c'est ce qui garde les
            # rangs alignés sur la liste publiée.
            continue
        geometrie = zone.get('geometry')
        if isinstance(geometrie, dict) and geometrie.get('mode') == 'free':
            if zone.get('id'):
                identifiants.add(zone['id'])
            rangs.add(rang)
        rang += 1
    return identifiants, rangs


def zones_publiees(layout_public):
    """Les zones du calepinage assaini, avec leur rang — dicts seulement."""
    return [(rang, zone)
            for rang, zone in enumerate((layout_public or {}).get('zones') or [])
            if isinstance(zone, dict)]


def nb_panneaux_publies(layout_public):
    """Le nombre de panneaux que le calepinage PUBLIÉ dessine réellement.

    C'est le compte que la page AFFICHE quand elle rend la clé racine
    ``roof_layout`` — donc le seul contre lequel une taille a le droit de dire
    « c'est exactement le calepinage du devis ». Compté sur TOUTES les zones
    publiées, y compris celles que la dérivation ne sait pas relire (voir
    :func:`lire_trames`) : sinon une zone illisible faisait sous-compter le
    toit, et la carte finissait par annoncer un nombre que son propre dessin ne
    montrait pas.
    """
    total = 0
    for _rang, zone in zones_publiees(layout_public):
        geometrie = zone.get('geometry')
        if not isinstance(geometrie, dict):
            continue
        panneaux = geometrie.get('panels')
        if isinstance(panneaux, list):
            total += sum(1 for p in panneaux if isinstance(p, dict))
    return total


def lire_trames(layout_public, libres=None):
    """Les trames EXPLOITABLES du calepinage assaini, dans l'ordre publié.

    Une zone publiée peut être illisible pour la dérivation (contour de moins
    de trois sommets valides, centres non finis…). Elle est alors absente
    d'ici — et :func:`deriver` en tire la conséquence : il ne dérive plus rien
    du tout, plutôt que de servir un dessin amputé de cette zone.
    """
    identifiants, rangs = libres if libres else (set(), set())
    trames = []
    for rang, zone in zones_publiees(layout_public):
        geometrie = zone.get('geometry')
        if not isinstance(geometrie, dict) or not geometrie.get('panels'):
            continue
        libre = (zone.get('id') in identifiants if zone.get('id')
                 else rang in rangs)
        trame = _Trame(rang, zone, geometrie, libre=libre)
        if trame.rangees and trame.anneau and len(trame.anneau) >= 3:
            trames.append(trame)
    return trames


def _repartir(trames, cible):
    """``({index de zone: [panneaux]}, nb dessiné)`` pour ``cible`` panneaux.

    RETRAIT — on enlève par la FIN de l'ordre canonique global : dernière zone,
    dernière rangée, ``u`` le plus grand d'abord. Déterministe et rejouable.

    EXTENSION — on prend les emplacements candidats zone par zone, dans l'ordre
    des zones, jusqu'à la cible. Ce qui manque encore à la fin est PLAFONNÉ par
    le toit : on le dit, on ne le dessine pas dehors.
    """
    ordre = [(trame.index, panneau)
             for trame in trames
             for panneau in trame.panneaux_ordonnes()]
    cible = max(0, min(int(cible), _MAX_PANNEAUX_DESSINES))

    if cible <= len(ordre):
        gardes = ordre[:cible]
    else:
        gardes = list(ordre)
        manque = cible - len(gardes)
        for trame in trames:
            if manque <= 0:
                break
            for panneau in trame.candidats(manque):
                gardes.append((trame.index, panneau))
                manque -= 1

    par_zone = {}
    for index, panneau in gardes:
        par_zone.setdefault(index, []).append(panneau)
    return par_zone, len(gardes)


def layout_derive(layout_public, par_zone):
    """Un ``roof_layout`` de MÊME FORME, portant les panneaux de cette taille.

    On repart de la sortie DÉJÀ ASSAINIE (whitelist QJ26/WJ24) : aucune clé
    nouvelle ne peut entrer par ici. ``result`` et ``pans`` sont volontairement
    ABSENTS — ce sont les totaux de l'installation VENDUE (kWc, kWh, panneaux
    par pan) ; les coller sur le dessin d'une autre taille afficherait les
    chiffres du devis sous un autre toit.
    """
    zones = []
    for rang, zone in zones_publiees(layout_public):
        nouvelle = {cle: zone[cle] for cle in _ZONE_RECOPIEES if cle in zone}
        if 'obstacles' in zone:
            # La clé SUIT la zone source (même vide : le calepinage dit alors
            # « ce pan n'a pas d'obstacle », ce qui n'est pas la même chose que
            # « on n'en sait rien »). Seuls les CHAMPS sont filtrés.
            nouvelle['obstacles'] = [
                {cle: o[cle] for cle in _OBSTACLE_RECOPIEES if cle in o}
                for o in zone['obstacles'] or [] if isinstance(o, dict)]
        panneaux = par_zone.get(rang) or []
        geometrie = zone.get('geometry')
        if panneaux and isinstance(geometrie, dict):
            geo = {cle: geometrie[cle] for cle in _GEO_RECOPIEES
                   if cle in geometrie}
            geo['count'] = len(panneaux)
            geo['panels'] = panneaux
            nouvelle['geometry'] = geo
        zones.append(nouvelle)
    if not zones:
        return None
    return {'version': 2, 'zones': zones}


def _dessin(trames, layout_public, cible, nb_publies, derivable, cache):
    """Le dict d'une option : ``origine``, ``layout``, ``plafonne``.

    L'ANCRE EST ``nb_publies``, PAS LE NOMBRE DE PANNEAUX RELISIBLES. Quand la
    taille demande EXACTEMENT ce que le calepinage PUBLIÉ dessine, le dessin
    EST le calepinage officiel : ``origine = 'devis'`` et AUCUN layout n'est
    transporté — la page réutilise la clé racine ``roof_layout``. Zéro copie,
    donc zéro dessin voisin capable de diverger de l'artefact contractuel.

    ``derivable`` faux (une zone publiée est illisible pour la dérivation) ⇒
    aucune AUTRE taille ne reçoit de dessin. C'est le choix explicite entre
    deux façons de se tromper : un dessin amputé de cette zone ferait dire à la
    carte « 22 panneaux » sous une image qui en montre 14, et l'absence
    honnête ne coûte que la vue de détail sur un cas rare.
    """
    cible = int(cible)
    if cible <= 0:
        return None
    if cible == nb_publies:
        return {'nb_panneaux': cible, 'nb_panneaux_dessines': cible,
                'origine': 'devis'}
    if not derivable:
        return None
    if cible in cache:
        dessine, layout = cache[cible]
    else:
        par_zone, dessine = _repartir(trames, cible)
        layout = layout_derive(layout_public, par_zone)
        cache[cible] = (dessine, layout)
    if not layout or not dessine:
        return None
    dessin = {'nb_panneaux': cible, 'nb_panneaux_dessines': dessine,
              'origine': 'derive', 'layout': layout}
    if dessine < cible:
        dessin['plafonne'] = True
    return dessin


# ════════════════════════════════════════════════════════════════════════════
# LE BLOC PUBLIC
# ════════════════════════════════════════════════════════════════════════════

def _design_stocke(devis):
    """La conception électrique STOCKÉE du devis, ou ``None``.

    Import paresseux : le module reste sans dépendance Django à l'import, et
    une lecture impossible ne coûte qu'un pointeur absent.
    """
    try:
        from .electrical_service import conception_electrique_stockee
        design = conception_electrique_stockee(devis)
    except Exception:  # noqa: BLE001 — pas de conception ⇒ pas de pointeur
        return None
    return design if isinstance(design, dict) else None


def _variante_du_design(design):
    """La variante que le schéma STOCKÉ dessine — ``'avec'``, ``'sans'``, None.

    L'ARTEFACT DIT LA VÉRITÉ, PAS LA CARTE. La question « ce schéma
    montre-t-il une batterie ? » a UNE réponse, et elle est écrite dans
    l'artefact lui-même : ``materiel.batterie.presente``
    (``electrical_service`` — ``bool(entree.batterie)`` au moment où le schéma
    a été calculé). La déduire du fait que la carte « Recommandé » sert une
    variante « avec » revenait à lire un signal COMMERCIAL pour légender un
    dessin TECHNIQUE, et les deux divergent pour de vrai :

    * la carte « avec » existe (les lignes servent l'option) mais la conception
      a été jouée sur le panier SANS batterie ⇒ un schéma raccordé réseau
      légendé « avec batterie » ;
    * l'artefact est ANTÉRIEUR à une resynchronisation qui a retiré la batterie
      ⇒ un schéma AVEC batterie légendé « sans ».

    Dans les deux cas la page affirmait au client un fait que le dessin sous
    ses yeux contredisait. On lit donc l'artefact ; illisible ⇒ pas de
    pointeur (absence honnête).
    """
    materiel = (design or {}).get('materiel')
    if not isinstance(materiel, dict):
        return None
    batterie = materiel.get('batterie')
    if not isinstance(batterie, dict) or 'presente' not in batterie:
        return None
    return 'avec' if batterie['presente'] else 'sans'


def _pointeur_sld(offres, sld_servi, design):
    """L'option que le schéma unifilaire DÉJÀ SERVI décrit — ou ``None``.

    Le devis ne stocke qu'UNE conception électrique
    (``Devis.electrical_design``), calculée pour UNE option par
    ``electrical_service._lignes_option_choisie`` (« avec » si les lignes la
    servent, sinon « sans »). Dessiner le schéma d'une AUTRE taille exigerait
    une NOUVELLE conception, c'est-à-dire un calcul et une écriture sur un
    chemin de LECTURE publique : interdit. On se contente donc de NOMMER
    l'option décrite ; la page affiche le schéma là, et l'omet ailleurs.

    Rien n'est nommé si aucun schéma n'est servi, si la carte du devis n'est
    plus le devis (``est_le_devis`` faux — le vendeur a ajusté cette taille),
    si l'artefact ne dit pas ce qu'il dessine (:func:`_variante_du_design`), ou
    si la carte ne sert pas la variante que l'artefact dessine.
    """
    if not sld_servi:
        return None
    reference = next((offre for offre in offres
                      if offre.get('cle') == 'recommande'
                      and offre.get('est_le_devis')), None)
    if reference is None:
        return None
    variante = _variante_du_design(design)
    if variante is None or not reference.get(variante):
        return None
    return {'cle': 'recommande', 'variante': variante}


def deriver(devis, offres_tailles, layout_public, sld_servi=False):
    """Le bloc ``calepinage_options`` complet, ou ``None``. PEUT lever.

    Les appelants publics passent par :func:`calepinage_options_publique`, qui
    pose le filet. Cette fonction reste nue pour que les tests voient l'erreur.
    """
    offres = list((offres_tailles or {}).get('offres') or [])
    if not offres:
        return None
    trames = lire_trames(layout_public, _modes_libres(devis))
    if not trames:
        return None
    # DEUX COMPTES, ET LA DIFFÉRENCE EST LE PIÈGE. ``nb_publies`` est ce que la
    # page DESSINE aujourd'hui pour ce devis (toutes les zones publiées) ;
    # ``nb_relisibles`` est ce que la dérivation sait manipuler. Ils ne
    # coïncident pas quand une zone publiée est illisible ici (contour trop
    # court, centres non finis). Ancrer « c'est le devis » sur le SECOND
    # laissait deux mensonges symétriques passer : une taille égale au vrai
    # posé partait en dérivé et perdait silencieusement la zone illisible, et
    # une taille égale au sous-compte se faisait étiqueter « c'est le devis »
    # alors que le calepinage racine en dessine davantage.
    nb_publies = nb_panneaux_publies(layout_public)
    nb_relisibles = sum(trame.nb_panneaux for trame in trames)
    if nb_publies <= 0:
        return None
    derivable = nb_relisibles == nb_publies

    cache, par_offre = {}, {}
    for offre in offres:
        cle = offre.get('cle')
        if not cle:
            continue
        dessins = {}
        for variante in ('sans', 'avec'):
            carte = offre.get(variante)
            if not isinstance(carte, dict):
                continue
            dessin = _dessin(trames, layout_public,
                             carte.get('nb_panneaux') or 0, nb_publies,
                             derivable, cache)
            if dessin is not None:
                dessins[variante] = dessin
        if dessins:
            par_offre[cle] = dessins
    if not par_offre:
        return None

    bloc = {'nb_panneaux_calepines': nb_publies, 'offres': par_offre}
    pointeur = _pointeur_sld(offres, sld_servi, _design_stocke(devis))
    if pointeur:
        bloc['sld'] = pointeur
    return bloc


def calepinage_options_publique(devis, offres_tailles, layout_public,
                                sld_servi=False):
    """Le bloc pour le payload public — best-effort, ne lève JAMAIS.

    MÊME patron que ``offres_tailles_publique`` / la garde
    ``_echelle_paliers_batterie_publique`` : toute exception est journalisée et
    la clé DISPARAÎT du payload. Un bloc additif ne fait jamais tomber la page
    d'un client.
    """
    try:
        return deriver(devis, offres_tailles, layout_public,
                       sld_servi=sld_servi)
    except Exception:  # noqa: BLE001
        logger.warning('calepinage_options indisponible', exc_info=True)
        return None


# ════════════════════════════════════════════════════════════════════════════
# ANNEXE « PARAMÈTRES DU SITE » (audit #23)
# ════════════════════════════════════════════════════════════════════════════

def _pan_principal(layout_public):
    """Le pan le PLUS PUISSANT du calepinage assaini, ou ``None``.

    Même lecture que ``services.extract_roof_config`` (qui retient déjà le pan
    le plus puissant comme orientation principale) : ``_pans_geometry``
    d'abord, la première zone exploitable ensuite.
    """
    pans = [pan for pan in (layout_public or {}).get('pans') or []
            if isinstance(pan, dict)]
    if pans:
        return max(pans, key=lambda p: _fini(p.get('kwc')) or 0.0)
    for zone in (layout_public or {}).get('zones') or []:
        if not isinstance(zone, dict):
            continue
        return {'azimut_deg': zone.get('facingAzimuthDeg'),
                'inclinaison_deg': zone.get('pitchDeg'),
                'roof_type': zone.get('roofType')}
    return None


def _matrice_ombrage_valide(matrice):
    """Exactement 12 × 24 facteurs finis dans [0, 1] — sinon ``False``.

    MÊME forme que le producteur (``prefill.serializeShading`` : 12 mois × 24
    heures, chaque facteur borné [0, 1]) et que le lecteur existant
    (``etude._valid_matrix``). Une matrice à moitié fausse est refusée EN BLOC.
    """
    if not isinstance(matrice, list) or len(matrice) != 12:
        return False
    for ligne in matrice:
        if not isinstance(ligne, list) or len(ligne) != 24:
            return False
        for facteur in ligne:
            valeur = _fini(facteur)
            if valeur is None or valeur < 0 or valeur > 1:
                return False
    return True


def _ombrage_mesure(devis):
    """``True`` seulement si une matrice d'ombrage 12 × 24 RÉELLE est stockée.

    LA CLÉ EST ``shading12x24``, PAS ``shading``. C'est le nom que le
    producteur écrit (``roofPro11/prefill.ts`` : ``shading12x24:
    serializeShading(ctx.shadeFactors)``) et celui que le lecteur backend
    existant interroge (``apps.ventes.etude`` : racine du layout ET par zone,
    « PV71 choisit encore où la matrice voyage côté web »). Lire ``shading``
    revenait à ne jamais rien trouver : le champ ``ombrage`` était du code
    mort, et son test se mentait à lui-même en injectant la clé fantôme.

    Mêmes deux emplacements que ``etude`` : la racine du layout, ou n'importe
    quelle zone.

    RÈGLE « ZÉRO CHIFFRE INVENTÉ », appliquée à la lettre : on ne publie AUCUN
    pourcentage de perte (l'agréger sur 288 facteurs serait un chiffre que
    personne n'a mesuré sous cette forme), et surtout aucun ombrage par défaut.
    Ce booléen dit un FAIT — « l'ombrage du voisinage a été relevé » — ou n'est
    pas publié du tout.
    """
    layout = getattr(devis, 'roof_layout', None)
    if not isinstance(layout, dict):
        return False
    if _matrice_ombrage_valide(layout.get('shading12x24')):
        return True
    for zone in layout.get('zones') or []:
        if isinstance(zone, dict) and _matrice_ombrage_valide(
                zone.get('shading12x24')):
            return True
    return False


def _chaines_publiques(conception_electrique):
    """Le résumé des chaînes — combien, et combien de modules sur chacune.

    Rien de neuf n'est publié : ``conception_electrique.chaines`` porte DÉJÀ
    ``nb_modules`` aux deux niveaux de partage (whitelist ``_PUBLIC_CHAINE``).
    L'annexe n'en fait qu'un résumé, sans jamais toucher aux calibres ni aux
    sections (qui, eux, sont dégradés au niveau standard et le restent).
    """
    chaines = [c for c in (conception_electrique or {}).get('chaines') or []
               if isinstance(c, dict)]
    modules = []
    for chaine in chaines:
        nombre = _fini(chaine.get('nb_modules'))
        if nombre is None or nombre <= 0:
            continue
        modules.append(int(nombre))
    if not modules:
        return None
    return {'nb': len(modules), 'modules_par_chaine': modules}


def parametres_site_publics(devis, layout_public, hypotheses=None,
                            conception_electrique=None):
    """AUDIT #23 — l'annexe « paramètres du site », ou ``None``.

    DES ANGLES ET DES NOMS, JAMAIS DES COORDONNÉES MACHINE : ni ``origin``, ni
    ``vertices``, ni latitude/longitude n'entrent ici (le contour reste dans
    ``roof_layout``, sous sa propre case de section).

    PAS DE SECOND ARRONDI : le productible n'est PAS republié — il vit déjà
    dans ``hypotheses.productible_net_kwh_kwc`` (bloc QK4, racine du payload).
    L'annexe ne fait que NOMMER la source (« PVGIS ») et la ville de la table.

    OMISSION PLUTÔT QUE SUBSTITUTION : chaque champ absent du stockage est
    absent de la sortie. Aucun défaut, aucun forfait — et surtout aucun
    ombrage supposé.

    Ne lève jamais : un bloc additif ne fait pas tomber la page d'un client.
    """
    try:
        annexe = {}
        pan = _pan_principal(layout_public)
        if pan:
            azimut = _fini(pan.get('azimut_deg'))
            if azimut is not None:
                annexe['orientation_deg'] = round(azimut, 1)
            inclinaison = _fini(pan.get('inclinaison_deg'))
            if inclinaison is not None:
                annexe['inclinaison_deg'] = round(inclinaison, 1)
            if pan.get('orientation'):
                annexe['orientation'] = str(pan['orientation'])
            if pan.get('roof_type'):
                annexe['type_toit'] = str(pan['roof_type'])
        ville = (hypotheses or {}).get('productible_ville')
        if ville:
            annexe['irradiation'] = {'source': 'PVGIS', 'ville': str(ville)}
        chaines = _chaines_publiques(conception_electrique)
        if chaines:
            annexe['chaines'] = chaines
        if _ombrage_mesure(devis):
            annexe['ombrage'] = {'mesure': True}
        return annexe or None
    except Exception:  # noqa: BLE001
        logger.warning('parametres_site indisponible', exc_info=True)
        return None
