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
  hors du contour ne peut pas exister ici : le test de contenance est fait sur
  une empreinte CONSERVATRICE (plus grande que le panneau réel), donc un
  emplacement douteux est REFUSÉ, jamais accordé.
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

#: Retrait de rive (m) exigé des quatre coins d'un emplacement AJOUTÉ. MÊME
#: valeur que le calepineur (``lib/roofPro2.ts`` ``PERIMETER_SETBACK_M`` et son
#: miroir visionneuse ``VIEWER_SETBACK_M``). Appliqué à une empreinte déjà plus
#: grande que le panneau réel : le test est donc STRICTEMENT plus sévère que
#: celui qui a posé le calepinage d'origine. On préfère toujours dessiner un
#: panneau de moins que dessiner un panneau dehors.
_RETRAIT_RIVE_M = 0.5

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

#: Les clés de zone NON recopiées sur un dessin dérivé. ``neededPanels`` est la
#: cible dimensionnée par l'étude du DEVIS : elle ne décrit pas la taille
#: explorée. ``geometry`` est reconstruite.
_ZONE_NON_RECOPIEES = ('neededPanels', 'geometry')


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
    """Les obstacles en boîtes ENU ``(xmin, ymin, xmax, ymax)``.

    L'orientation d'un obstacle n'est PAS stockée : on le traite comme une
    boîte alignée Est/Nord de ``lengthM`` × ``widthM``. C'est conservateur dans
    le sens utile (on refuse un peu large autour d'une cheminée), jamais
    l'inverse.
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
        longueur = _fini(obstacle.get('lengthM'))
        largeur = _fini(obstacle.get('widthM'))
        if None in (lng, lat, longueur, largeur):
            continue
        if longueur <= 0 or largeur <= 0:
            continue
        cx = (lng - olng) * _DEG2M * cos_lat
        cy = (lat - olat) * _DEG2M
        boites.append((cx - longueur / 2.0, cy - largeur / 2.0,
                       cx + longueur / 2.0, cy + largeur / 2.0))
    return boites


# ════════════════════════════════════════════════════════════════════════════
# LA TRAME RÉELLE D'UNE ZONE
# ════════════════════════════════════════════════════════════════════════════

class _Trame:
    """La pose RÉELLE d'une zone, lue en rangées.

    ``rangees`` : liste ``[(v, [(u, panneau), …]), …]`` triée ``v`` croissant,
    chaque rangée triée ``u`` croissant. ``panneau`` est le dict publiable
    d'origine (``{cx, cy, face?}``) — recopié tel quel, jamais reconstruit :
    un panneau CONSERVÉ garde sa position au bit près.
    """

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
            uu, vv = _vers_uv(cx, cy, self.u, self.s)
            cellules.append((vv, uu, panneau))
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
                if ecart > 1e-6 and (pas is None or ecart < pas):
                    pas = ecart
        return pas

    def _pas_rangee(self):
        pas = None
        for i in range(1, len(self.rangees)):
            ecart = self.rangees[i][0] - self.rangees[i - 1][0]
            if ecart > 1e-6 and (pas is None or ecart < pas):
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
    def extensible(self):
        """Peut-on PROLONGER cette zone sans deviner ?

        Il faut les DEUX pas (colonne et rangée) : sans le pas de rangée on ne
        connaît pas la profondeur occupée par un panneau, donc on ne peut pas
        prouver qu'un ajout tient dans le polygone. Une zone à une seule rangée
        (ou posée À LA MAIN, ``mode == 'free'``) n'est donc jamais prolongée —
        le dessin plafonne, et il le DIT.
        """
        return (not self.libre and bool(self.rangees)
                and self.pas_colonne is not None
                and self.pas_rangee is not None)

    def _emplacement_libre(self, uu, vv):
        """Les quatre coins d'une empreinte CONSERVATRICE tiennent-ils ?

        L'empreinte vaut ``pas_colonne`` × ``pas_rangee`` : par construction
        elle est PLUS GRANDE que le panneau réel (le pas inclut le jeu entre
        panneaux, et le pas de rangée inclut l'ombre portée sur toit plat).
        Un emplacement accepté ici l'aurait donc été par le calepineur ; un
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
    """``{index de zone: True}`` pour les zones posées À LA MAIN.

    ``geometry.mode == 'free'`` (PV30) n'est PAS republié par la whitelist
    publique : on va donc le chercher sur le blob stocké, et lui seul. Une
    lecture ratée vaut « pas libre » — au pire on refuse d'étendre une zone
    qu'on aurait pu étendre, jamais l'inverse.
    """
    libres = {}
    layout = getattr(devis, 'roof_layout', None)
    if not isinstance(layout, dict):
        return libres
    for index, zone in enumerate(layout.get('zones') or []):
        if not isinstance(zone, dict):
            continue
        geometrie = zone.get('geometry')
        if isinstance(geometrie, dict) and geometrie.get('mode') == 'free':
            libres[index] = True
    return libres


def lire_trames(layout_public, libres=None):
    """Les trames exploitables du calepinage ASSAINI, dans l'ordre stocké."""
    libres = libres or {}
    trames = []
    for index, zone in enumerate((layout_public or {}).get('zones') or []):
        if not isinstance(zone, dict):
            continue
        geometrie = zone.get('geometry')
        if not isinstance(geometrie, dict) or not geometrie.get('panels'):
            continue
        trame = _Trame(index, zone, geometrie, libre=libres.get(index, False))
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
    for index, zone in enumerate((layout_public or {}).get('zones') or []):
        if not isinstance(zone, dict):
            continue
        nouvelle = {cle: valeur for cle, valeur in zone.items()
                    if cle not in _ZONE_NON_RECOPIEES}
        panneaux = par_zone.get(index) or []
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


def _dessin(trames, layout_public, cible, nb_reel, cache):
    """Le dict d'une option : ``origine``, ``layout``, ``plafonne``.

    Quand la taille demande EXACTEMENT le nombre de panneaux réellement posés,
    le dessin EST le calepinage officiel : ``origine = 'devis'`` et AUCUN
    layout n'est transporté — la page réutilise la clé racine ``roof_layout``.
    Zéro copie, donc zéro dessin voisin capable de diverger de l'artefact
    contractuel.
    """
    cible = int(cible)
    if cible <= 0:
        return None
    if cible == nb_reel:
        return {'nb_panneaux': cible, 'nb_panneaux_dessines': cible,
                'origine': 'devis'}
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

def _pointeur_sld(offres, sld_servi):
    """L'option que le schéma unifilaire DÉJÀ SERVI décrit — ou ``None``.

    Le devis ne stocke qu'UNE conception électrique
    (``Devis.electrical_design``), calculée pour UNE option par
    ``electrical_service._lignes_option_choisie`` (« avec » si les lignes la
    servent, sinon « sans »). Dessiner le schéma d'une AUTRE taille exigerait
    une NOUVELLE conception, c'est-à-dire un calcul et une écriture sur un
    chemin de LECTURE publique : interdit. On se contente donc de NOMMER
    l'option décrite ; la page affiche le schéma là, et l'omet ailleurs.

    Rien n'est nommé si aucun schéma n'est servi, ou si la carte du devis n'est
    plus le devis (``est_le_devis`` faux — le vendeur a ajusté cette taille).
    """
    if not sld_servi:
        return None
    reference = next((offre for offre in offres
                      if offre.get('cle') == 'recommande'
                      and offre.get('est_le_devis')), None)
    if reference is None:
        return None
    variante = 'avec' if reference.get('avec') else 'sans'
    if not reference.get(variante):
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
    nb_reel = sum(trame.nb_panneaux for trame in trames)
    if nb_reel <= 0:
        return None

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
                             carte.get('nb_panneaux') or 0, nb_reel, cache)
            if dessin is not None:
                dessins[variante] = dessin
        if dessins:
            par_offre[cle] = dessins
    if not par_offre:
        return None

    bloc = {'nb_panneaux_calepines': nb_reel, 'offres': par_offre}
    pointeur = _pointeur_sld(offres, sld_servi)
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


def _ombrage_mesure(devis):
    """``True`` seulement si une matrice d'ombrage 12 × 24 RÉELLE est stockée.

    RÈGLE « ZÉRO CHIFFRE INVENTÉ », appliquée à la lettre : on ne publie AUCUN
    pourcentage de perte (l'agréger sur 288 facteurs serait un chiffre que
    personne n'a mesuré sous cette forme), et surtout aucun ombrage par défaut.
    Ce booléen dit un FAIT — « l'ombrage du voisinage a été relevé » — ou n'est
    pas publié du tout.
    """
    layout = getattr(devis, 'roof_layout', None)
    if not isinstance(layout, dict):
        return False
    matrice = layout.get('shading')
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
