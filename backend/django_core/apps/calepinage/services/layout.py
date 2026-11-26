"""CAL13 / ACAL39 — enregistrer une conception : DEUX empreintes, deux usages.

DEUX EMPREINTES (D-ACAL-4 + D-ACAL-21), JAMAIS CONFONDUES
---------------------------------------------------------
* **L'empreinte « document »** — :func:`empreinte_document`, définie ICI et
  nulle part ailleurs : SHA-256 du document ENTIER (JSON trié), moins les
  seules clés VOLATILES nommées dans :data:`CLES_VOLATILES` (état d'écran qui
  ne change rien à la conception). Elle décide « inchangé », la version et le
  journal : un horizon dessiné, un champ au sol retiré, une épingle recentrée
  (D-ACAL-13) sont des changements de conception, même quand le devis n'en
  voit rien. Le jeton If-Match (C-ACAL-044) et l'empreinte de simulation
  (C-ACAL-073) la RÉUTILISERONT — jamais une seconde fonction.
* **L'empreinte « imprimée »** — ``apps.ventes.services.layout_hash`` (corps
  réel dans ``apps/ventes/domain/geometrie.py``), stockée dans
  ``Calepinage.layout_hash`` : elle ne couvre que ce qui change un chiffre que
  le client voit, et sert à la péremption du devis et à la dédup. Elle n'est
  pas recodée ici : on l'IMPORTE.

CE QUE FAIT LE SERVICE
----------------------
1. il pose ``roof_layout`` sur le pivot ;
2. il RECALCULE ``layout_hash`` (empreinte imprimée) par le ré-export ventes ;
3. il crée une ``CalepinageVersion`` et une ligne de journal **seulement si
   l'empreinte DOCUMENT a changé** — un enregistrement à l'identique (double
   clic, renvoi réseau, simple changement d'état d'écran) ne pollue pas
   l'historique et répond ``inchange: True``.

Aucun statut de devis n'est jamais écrit (règle #4), et la société/l'auteur
sont posés côté serveur.
"""
from __future__ import annotations


import hashlib
import math
import json

from core.conflit_etat import ConflitEtat
from core.events import pose_enregistree

#: ACAL39 — les SEULES clés « volatiles » du document : état d'écran qui ne
#: change rien à la conception, donc hors empreinte « document ». Chaque
#: entrée est un CHEMIN ; ``[]`` parcourt une liste. Les pans se lisent aussi
#: sous les alias historiques ``areas`` / ``pans`` (même règle que l'empreinte
#: imprimée).
#:
#: * ``activeAreaId`` — le pan sélectionné à l'écran ;
#: * ``scene`` — l'instant du soleil affiché ({sunDay, sunHour}, CALX88) : un
#:   point de vue, aucun calcul n'en dépend ;
#: * ``zones[].geometry.solarAccess.computedAt`` — l'horodatage d'un calcul,
#:   pas son résultat ;
#: * ``consumption.source.saisi_le`` — l'horodatage d'une saisie, pas la
#:   saisie ;
#: * ``plafondsNumerotation`` — numérotation stable (suite ACAL1720) : le plus
#:   haut numéro de module jamais attribué par pan, TENUE DE COMPTE de
#:   l'atelier (aucun module, aucun chiffre) ; elle ne bouge qu'avec un retrait
#:   de modules, déjà versionné par ``zones``.
#:
#: ``pin`` n'y est PAS : un recentrage de l'épingle est versionné (D-ACAL-13).
CLES_VOLATILES = (
    'activeAreaId',
    'scene',
    'zones[].geometry.solarAccess.computedAt',
    'consumption.source.saisi_le',
    'plafondsNumerotation',
)

_ALIAS_PANS = ('zones', 'areas', 'pans')


def _retirer_chemin(noeud, morceaux):
    """Retire, EN PLACE (sur une copie), la clé désignée par ``morceaux``."""
    if not morceaux or not isinstance(noeud, dict):
        return
    tete, reste = morceaux[0], morceaux[1:]
    liste = tete.endswith('[]')
    cle = tete[:-2] if liste else tete
    if cle not in noeud:
        return
    if not reste:
        noeud.pop(cle, None)
        return
    valeur = noeud[cle]
    if liste:
        for element in valeur if isinstance(valeur, list) else ():
            _retirer_chemin(element, reste)
    else:
        _retirer_chemin(valeur, reste)


def _document_sans_volatiles(roof_layout):
    """Une COPIE du document, privée des seules :data:`CLES_VOLATILES`."""
    import copy

    document = copy.deepcopy(roof_layout)
    for chemin in CLES_VOLATILES:
        morceaux = chemin.split('.')
        if morceaux[0] == 'zones[]':
            for alias in _ALIAS_PANS:
                _retirer_chemin(document, [f'{alias}[]'] + morceaux[1:])
        else:
            _retirer_chemin(document, morceaux)
    return document


def layout_decrit_une_geometrie(layout):
    """Ce ``roof_layout`` décrit-il une géométrie RÉELLEMENT exploitable ?

    ACAL114 — déplacé de ``views/calepinages.py`` (un service n'importe
    jamais une vue, R3) : l'approbation le lit aussi (« rien à approuver »).


    Pas « contient-il une clé ``zones`` », mais « un pan y porte-t-il au moins
    trois sommets ». La nuance est TOUT le correctif du 20/09/2026 : le
    sérialiseur de l'atelier (``apps/web/src/scripts/roofPro11/prefill.ts``,
    ``serializeLayout``) émet TOUJOURS une zone — il projette ``ctx.areas``,
    qui contient la zone par défaut même quand personne n'a encore tracé quoi
    que ce soit. Un premier « Enregistrer le calepinage » fait avant tout
    dessin écrit donc ``{outline: [], zones: [{vertices: []}]}`` : un layout
    qui ne dit RIEN de la géométrie, mais que l'ancien test (« ``zones``
    présent ? ») lisait comme un calepinage déjà dessiné. Le tracé du client
    était alors jeté (``outline: []``), l'atelier ne trouvait ni pan ni
    contour, retombait sur l'épingle seule et affichait « tracez le contour du
    toit pour lancer le calcul » — aucun pan, aucune recommandation, aucune
    requête de rendement.
    """
    if not isinstance(layout, dict):
        return False
    contour = layout.get('outline')
    if isinstance(contour, list) and len(contour) >= 3:
        return True
    for cle in ('zones', 'areas'):
        zones = layout.get(cle)
        if not isinstance(zones, list):
            continue
        for zone in zones:
            sommets = zone.get('vertices') if isinstance(zone, dict) else None
            if isinstance(sommets, list) and len(sommets) >= 3:
                return True
    return False


def empreinte_document(roof_layout):
    """ACAL39 — l'empreinte « document » (D-ACAL-4) : SHA-256 hex du JSON trié.

    Tout le document compte, sauf :data:`CLES_VOLATILES`. Un document absent
    (``None``) rend ``''`` : « rien » n'a pas d'empreinte. Fonction PURE.
    """
    if roof_layout is None:
        return ''
    canonique = json.dumps(_sans_obstacles_hors_toit(_document_sans_volatiles(roof_layout)),
                           sort_keys=True, separators=(',', ':'),
                           ensure_ascii=False, default=str)
    return hashlib.sha256(canonique.encode('utf-8')).hexdigest()


def _segments_se_coupent(a, b, c, d):
    """Les segments [a, b] et [c, d] (mètres) se coupent-ils (contact compris) ?"""
    def orient(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    def sur(p, q, r):
        return min(p[0], q[0]) <= r[0] <= max(p[0], q[0]) and min(p[1], q[1]) <= r[1] <= max(p[1], q[1])

    o1, o2, o3, o4 = orient(a, b, c), orient(a, b, d), orient(c, d, a), orient(c, d, b)
    if (o1 > 0) != (o2 > 0) and (o3 > 0) != (o4 > 0) and 0 not in (o1, o2, o3, o4):
        return True
    return any(o == 0 and sur(p, q, r) for o, p, q, r in ((o1, a, b, c), (o2, a, b, d), (o3, c, d, a), (o4, c, d, b)))


def _disjoints(obstacle, pan):
    """Deux contours (mètres) sans aucun point commun : aucun sommet de l'un dans l'autre,
    aucune arête qui en coupe une autre."""
    from core.calepinage.geometrie import point_dans_polygone

    if any(point_dans_polygone(p, pan) for p in obstacle) or any(
            point_dans_polygone(p, obstacle) for p in pan):
        return False
    aretes = [(obstacle[i], obstacle[i - 1]) for i in range(len(obstacle))]
    return not any(_segments_se_coupent(a, b, pan[j], pan[j - 1]) for a, b in aretes for j in range(len(pan)))


def _sans_obstacles_hors_toit(document):
    """T4-X2-002 — le document de l'EMPREINTE, privé des obstacles ENTIÈREMENT hors de tout pan
    (l'atelier le dit : « il n'a aucun effet ici »). Géométrie illisible, sans projection ou
    obstacle qui touche un pan : rien n'est retiré. Un document sans tel obstacle est rendu TEL
    QUEL (même objet) : son empreinte ne bouge pas d'un bit."""
    from .planche import _points_geo, _projection, _zones
    from .pret_a_envoyer import _points_de_l_obstacle

    zones = _zones(document) if isinstance(document, dict) else []
    projection = _projection(document) if zones else None
    if projection is None:
        return document
    pans = [[projection.vers_local(lat, lng) for lat, lng in _points_geo(z.get('vertices'), 'lnglat')]
            for z in zones]
    pans = [pan for pan in pans if len(pan) >= 3]

    def hors_toit(obstacle):
        points = _points_de_l_obstacle(obstacle, projection.vers_local) if isinstance(obstacle, dict) else None
        if not pans or not points or len(points) < 3:
            return False
        if obstacle.get('forme') != 'polygone':  # rectangle, disque : sommets remis dans l'ordre du tour
            cx, cy = sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points)
            points = sorted(points, key=lambda p: math.atan2(p[1] - cy, p[0] - cx))
        return all(_disjoints(points, pan) for pan in pans)
    if not any(hors_toit(o) for z in zones if isinstance(z.get('obstacles'), list) for o in z['obstacles']):
        return document
    for zone in zones:
        if isinstance(zone.get('obstacles'), list):
            zone['obstacles'] = [o for o in zone['obstacles'] if not hors_toit(o)]
    return document


#: Numérotation stable (suite ACAL1720) — la clé racine des plafonds de
#: numérotation (même nom que ``roofPro11/numerotation.ts::CLE_PLAFONDS``).
CLE_PLAFONDS_NUMEROTATION = 'plafondsNumerotation'


def _plafonds_du_document(roof_layout):
    """``({pan: plafond}, {pan: plus haut n posé})`` d'un document : le plafond
    est le plus grand de la clé ``plafondsNumerotation`` et des ``n`` posés."""
    plafonds, poses = {}, {}
    if not isinstance(roof_layout, dict):
        return plafonds, poses
    lus = roof_layout.get(CLE_PLAFONDS_NUMEROTATION)
    for pan, valeur in (lus.items() if isinstance(lus, dict) else ()):
        if isinstance(valeur, int) and not isinstance(valeur, bool) and valeur >= 1:
            plafonds[pan] = max(plafonds.get(pan, 0), valeur)
    zones = next((roof_layout[a] for a in _ALIAS_PANS
                  if isinstance(roof_layout.get(a), list)), [])
    for zone in zones:
        pan = zone.get('id') if isinstance(zone, dict) else None
        geometrie = zone.get('geometry') if isinstance(zone, dict) else None
        panneaux = geometrie.get('panels') if isinstance(geometrie, dict) else None
        if not isinstance(pan, str) or not pan:
            continue
        haut = max((p['n'] for p in (panneaux if isinstance(panneaux, list) else ())
                    if isinstance(p, dict) and isinstance(p.get('n'), int)
                    and not isinstance(p.get('n'), bool)), default=0)
        poses[pan] = max(poses.get(pan, 0), haut)
        plafonds[pan] = max(plafonds.get(pan, 0), haut)
    return plafonds, poses


def avec_plafonds_gardes(remplace, entrant):
    """Numérotation stable (suite ACAL1720, revue lot 8) — ``entrant`` (le
    document qui va REMPLACER ``remplace`` : version restaurée, variante
    retenue) avec, par pan, ``plafondsNumerotation`` = le plus grand des deux
    plafonds (clé, sinon plus haut ``n``), écrit SEULEMENT quand il dépasse le
    plus haut ``n`` posé d'``entrant`` (même règle que l'atelier). Sans cela,
    les numéros dépensés depuis la version seraient redonnés à d'autres
    panneaux et une affectation manuelle ``<pan>#<n>`` les viserait.

    Clé VOLATILE (:data:`CLES_VOLATILES`) : ni l'empreinte « document », ni
    ``layout_hash`` ne bougent. Rend ``entrant`` LUI-MÊME quand il n'y a rien
    à changer, une copie sinon ; ``entrant`` n'est jamais modifié."""
    import copy

    if not isinstance(entrant, dict):
        return entrant
    anciens, _ = _plafonds_du_document(remplace)
    neufs, poses = _plafonds_du_document(entrant)
    plafonds = {}
    for pan in sorted(set(anciens) | set(neufs)):
        plafond = max(anciens.get(pan, 0), neufs.get(pan, 0))
        if plafond > poses.get(pan, 0):
            plafonds[pan] = plafond
    if plafonds == entrant.get(CLE_PLAFONDS_NUMEROTATION) or (
            not plafonds and CLE_PLAFONDS_NUMEROTATION not in entrant):
        return entrant
    sortie = copy.deepcopy(entrant)
    if plafonds:
        sortie[CLE_PLAFONDS_NUMEROTATION] = plafonds
    else:
        sortie.pop(CLE_PLAFONDS_NUMEROTATION, None)
    return sortie


def _est_nombre(valeur):
    return isinstance(valeur, (int, float)) and not isinstance(valeur, bool)


def garder_types_numeriques(ancien, nouveau):
    """ERR-ACAL351 — ``nouveau`` où chaque nombre ÉGAL en valeur au nombre
    stocké au même chemin garde le TYPE stocké (``15`` reçu sur ``15.0``
    stocké ⇒ ``15.0``, et inversement). Fonction PURE (copie).

    L'atelier re-sérialise ``15.0`` en ``15`` (JSON JavaScript) : sans cela,
    un premier « Enregistrer » sans geste d'un document écrit en Python
    changeait les octets du document, donc l'empreinte « document », et
    déposait une version fantôme. Les empreintes elles-mêmes ne sont PAS
    recodées : leurs valeurs déjà stockées (jeton, simulation, images,
    livrables, ``layout_hash``) restent justes pour tout document inchangé.
    """
    if _est_nombre(ancien) and _est_nombre(nouveau):
        return ancien if (type(ancien) is not type(nouveau)
                          and ancien == nouveau) else nouveau
    if isinstance(ancien, dict) and isinstance(nouveau, dict):
        return {cle: (garder_types_numeriques(ancien[cle], valeur)
                      if cle in ancien else valeur)
                for cle, valeur in nouveau.items()}
    if isinstance(ancien, list) and isinstance(nouveau, list):
        return [garder_types_numeriques(ancien[i], valeur)
                if i < len(ancien) else valeur
                for i, valeur in enumerate(nouveau)]
    return nouveau


class LayoutRefuse(ValueError):
    """Refus métier d'enregistrement, message français, champ fautif nommé."""

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ


class LayoutCaractereInterdit(ConflitEtat):
    """409 - U+0000 ou un demi-substitut isole dans le document de conception
    (cle OU valeur, a toute profondeur). Le document est un objet libre dont
    le schema OpenAPI ne borne ni les cles ni les textes imbriques : refus
    d'ETAT inexprimable au schema, donc 409 et non 400 (ENF11, meme doctrine
    que ``parametres.CaractereInterditEnCle``)."""

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ


def _contour_lisible(sommets):
    """Le contour en couples numériques, ou ``None`` s'il est illisible."""
    if not isinstance(sommets, list):
        return None
    pts = []
    for point in sommets:
        if (not isinstance(point, (list, tuple)) or len(point) < 2
                or not all(isinstance(v, (int, float))
                           and not isinstance(v, bool) for v in point[:2])):
            return None
        pts.append((point[0], point[1]))
    return pts


def contours_croises(document):
    """ACAL76 — ``[(chemin, contour), …]`` des contours qui se CROISENT.

    Contours contrôlés : ``zones[].vertices``, ``zones[].obstacles[].contour``,
    ``exclusionZones[].vertices`` et ``poseSurfaces[].vertices`` ; le test est
    ``core.calepinage.geometrie.est_polygone_simple`` (le noyau, jamais
    recodé). Un contour illisible est laissé au schéma. Fonction PURE.
    """
    from core.calepinage.geometrie import est_polygone_simple

    if not isinstance(document, dict):
        return []
    candidats = []
    zones = document.get('zones')
    for rang, zone in enumerate(zones if isinstance(zones, list) else ()):
        if not isinstance(zone, dict):
            continue
        candidats.append((f'zones.{rang}.vertices', zone.get('vertices')))
        obstacles = zone.get('obstacles')
        for place, obstacle in enumerate(
                obstacles if isinstance(obstacles, list) else ()):
            if isinstance(obstacle, dict):
                candidats.append(
                    (f'zones.{rang}.obstacles.{place}.contour',
                     obstacle.get('contour')))
    exclusions = document.get('exclusionZones')
    for rang, zone in enumerate(
            exclusions if isinstance(exclusions, list) else ()):
        if isinstance(zone, dict):
            candidats.append((f'exclusionZones.{rang}.vertices',
                              zone.get('vertices')))
    # ACON8 — le champ au sol (D-ACAL-5 : compté au devis) aussi.
    surfaces = document.get('poseSurfaces')
    for rang, surface in enumerate(
            surfaces if isinstance(surfaces, list) else ()):
        if isinstance(surface, dict):
            candidats.append((f'poseSurfaces.{rang}.vertices',
                              surface.get('vertices')))
    croises = []
    for chemin, sommets in candidats:
        contour = _contour_lisible(sommets)
        if contour and not est_polygone_simple(contour):
            croises.append((chemin, contour))
    return croises


def message_contour_croise(chemin):
    """ACAL76 — le refus nommé d'un contour qui se croise."""
    return (f"Conception refusée au champ « {chemin} » : le contour se "
            "croise (nœud papillon) — redessinez-le sans que deux côtés se "
            "coupent.")


def _refuser_contour_nouvellement_croise(ancien, nouveau):
    """ACAL76 — refuse un contour croisé ABSENT du document stocké.

    Un contour croisé DÉJÀ stocké et renvoyé inchangé passe : on ne bloque
    jamais l'édition d'un dossier existant pour un défaut ancien.
    """
    croises = contours_croises(nouveau)
    if not croises:
        return
    deja = {json.dumps(contour) for _c, contour in contours_croises(ancien)}
    for chemin, contour in croises:
        if json.dumps(contour) not in deja:
            raise LayoutRefuse(message_contour_croise(chemin), champ=chemin)


def _refuser_nature_nouvellement_inconnue(ancien, nouveau):
    """ACAL312 (D-ACAL-20) — refuse une zone d'exclusion dont la nature n'est
    pas admise (``services.zones.natures_admises``, le noyau), au chemin
    ``exclusionZones.<i>.nature``.

    Même patron qu'ACAL76 : une zone DÉJÀ stockée et renvoyée inchangée
    passe — on ne bloque jamais la réédition d'un dossier existant pour un
    défaut ancien (pass-through octet-identique).

    La zone est comparée HORS de ses coordonnées géographiques (les clés que
    ``services.repere.CHEMINS_TRANSLATES`` translate sous ``exclusionZones``) :
    le défaut est la NATURE, et un déplacement de la géométrie seule — le
    recentrage sur le lead (ACAL191), translation pure — n'introduit aucune
    nature nouvelle. Toute autre clé modifiée (nature comprise) refait
    passer la zone par le refus.
    """
    from .repere import CHEMINS_TRANSLATES
    from .zones import CLE_LAYOUT, message_nature_inconnue, natures_inconnues

    refusees = natures_inconnues(nouveau)
    if not refusees:
        return

    prefixe = f'{CLE_LAYOUT}[].'
    geometrie = {chemin[len(prefixe):].split('.')[0]
                 for chemin in CHEMINS_TRANSLATES if chemin.startswith(prefixe)}

    def _zone(document, chemin):
        rang = int(chemin.split('.')[1])
        zone = document[CLE_LAYOUT][rang]
        return json.dumps({cle: valeur for cle, valeur in zone.items()
                           if cle not in geometrie},
                          sort_keys=True, default=str)

    deja = {_zone(ancien, chemin) for chemin, _n in natures_inconnues(ancien)}
    for chemin, nature in refusees:
        if _zone(nouveau, chemin) not in deja:
            raise LayoutRefuse(message_nature_inconnue(chemin, nature),
                               champ=chemin)


class DocumentModifie(ValueError):
    """ACAL22 (C-ACAL-044) — le jeton d'écriture est périmé.

    Le document a été modifié ailleurs (un onglet, un autre navigateur)
    depuis que l'écrivain l'a lu : son ``base_empreinte`` / ``If-Match`` ne
    correspond plus à l'empreinte « document » STOCKÉE. Rien n'est écrit ; la
    vue répond 409 ``{detail, code: 'document_modifie', empreinte_courante}``
    (contrat ``calepinage_layout_section.json``).
    """

    code = 'document_modifie'
    message = ("Le document a été modifié ailleurs depuis votre ouverture : "
               "rechargez avant d'enregistrer.")

    def __init__(self, empreinte_courante):
        super().__init__(self.message)
        self.empreinte_courante = empreinte_courante

    def corps(self):
        return {'detail': self.message, 'code': self.code,
                'empreinte_courante': self.empreinte_courante}


#: ACAL316 / ACON9 — LE 428 d'une écriture COMPLÈTE sans jeton If-Match (porte
#: du module ET portes ventes ``sync-layout`` / ``layout`` d'un devis conçu).
MESSAGE_JETON_VERSION_MANQUANT = ("Jeton de version manquant : rechargez la "
                                  "conception avant d'enregistrer.")

#: ACAL22 / ACON2 — LE message d'un jeton d'écriture absent (section, cote).
MESSAGE_JETON_MANQUANT = ("Jeton manquant : envoyez base_empreinte, "
                          "l'empreinte du document ouvert.")

#: ACAL22 — les SEULES clés racine qu'une écriture par section remplace.
CLES_SECTION_RACINE = ('horizonProfile', 'poseSurfaces', 'underlay',
                       'alleeTechnique')
#: ACAL22 — la section ``zones`` : les SEULS champs d'UNE zone qu'elle écrit.
#: ACAL206 — l'azimut posé depuis un relevé/une visite porte sa PROVENANCE
#: (``facingAzimuthSource``) et sa PRÉCISION (``facingAzimuthPrecisionDeg``) :
#: les deux s'écrivent avec lui, par la même primitive.
CHAMPS_SECTION_ZONE = ('pitchDeg', 'pitchSource', 'facingAzimuthDeg',
                       'facingManual', 'facingAzimuthSource',
                       'facingAzimuthPrecisionDeg')


def _relire_sous_verrou(calepinage, base_empreinte):
    """Relit le document STOCKÉ sous verrou de ligne et compare le jeton.

    À appeler DANS ``transaction.atomic``. ``select_for_update`` : deux
    écrivains concurrents se sérialisent — le second relit le document du
    premier et voit son jeton périmé (409) au lieu de l'écraser.
    """
    from ..models import Calepinage

    stocke = (Calepinage.objects.select_for_update()
              .only('pk', 'roof_layout').get(pk=calepinage.pk))
    courante = empreinte_document(stocke.roof_layout)
    if base_empreinte != courante:
        raise DocumentModifie(courante)
    return stocke.roof_layout


def enregistrer_section(calepinage, cle, valeur, *, base_empreinte,
                        zone_id=None, user=None):
    """ACAL22 — écrit UNE section du document, jamais le document entier.

    * ``cle`` ∈ :data:`CLES_SECTION_RACINE` : la clé racine est REMPLACÉE par
      ``valeur`` (``None`` la retire) ;
    * ``cle == 'zones'`` : ``valeur`` est un objet de champs ⊂
      :data:`CHAMPS_SECTION_ZONE`, posés sur la SEULE zone ``zone_id``.

    Le document stocké est relu sous verrou de ligne et ``base_empreinte`` est
    comparé à son empreinte « document » (jamais ``layout_hash``) :
    différent ⇒ :class:`DocumentModifie` (409), rien n'est écrit. L'écriture
    passe ensuite par :func:`enregistrer_layout` (seul écrivain : version si
    changement, verrou CAL207 inchangé), dans la MÊME transaction.

    Raises:
        LayoutRefuse: clé hors liste blanche (``champ='cle'``), champ de zone
            hors liste (``champ='champs'``), zone introuvable
            (``champ='zone_id'``), jeton absent (``champ='base_empreinte'``).
        DocumentModifie: jeton périmé.
    """
    import copy

    from django.db import transaction

    if calepinage is None or not getattr(calepinage, 'pk', None):
        raise LayoutRefuse(
            "Le calepinage n'est pas encore enregistré : impossible d'y "
            "enregistrer une conception.", champ='calepinage')
    if cle not in CLES_SECTION_RACINE and cle != 'zones':
        raise LayoutRefuse(
            "Clé non autorisée : seules horizonProfile, poseSurfaces, "
            "underlay, alleeTechnique et zones s'écrivent par section.",
            champ='cle')
    # ACAL360 — ``''`` est le jeton d'un document encore vide (comme
    # ``If-Match: ""`` d'ACAL316) ; seul un jeton absent / non texte est refusé.
    if not isinstance(base_empreinte, str):
        raise LayoutRefuse(MESSAGE_JETON_MANQUANT, champ='base_empreinte')
    if cle == 'zones':
        if not isinstance(valeur, dict) or not valeur:
            raise LayoutRefuse(
                "Champs de zone manquants : un objet est attendu.",
                champ='champs')
        hors_liste = sorted(set(valeur) - set(CHAMPS_SECTION_ZONE))
        if hors_liste:
            raise LayoutRefuse(
                "Champ de zone non autorisé : " + ', '.join(hors_liste)
                + " (seuls " + ', '.join(CHAMPS_SECTION_ZONE)
                + " s'écrivent par section).", champ='champs')
        if zone_id in (None, ''):
            raise LayoutRefuse("Zone manquante : zone_id est obligatoire.",
                               champ='zone_id')

    with transaction.atomic():
        stocke = _relire_sous_verrou(calepinage, base_empreinte)
        document = copy.deepcopy(stocke) if isinstance(stocke, dict) else {}
        if cle == 'zones':
            zones = document.get('zones')
            zone = None
            if isinstance(zones, list):
                zone = next((z for z in zones if isinstance(z, dict)
                             and str(z.get('id')) == str(zone_id)), None)
            if zone is None:
                raise LayoutRefuse(
                    f"Zone introuvable dans la conception : {zone_id}.",
                    champ='zone_id')
            zone.update(copy.deepcopy(valeur))
        elif valeur is None:
            document.pop(cle, None)
        else:
            document[cle] = copy.deepcopy(valeur)
        return enregistrer_layout(calepinage, document, user=user,
                                  base_empreinte=base_empreinte)


def enregistrer_layout(calepinage, roof_layout, *, user=None,
                       libelle='', resultat=None, roof_image=None,
                       version_moteur=None, base_empreinte=None,
                       valider_factures=False):
    """Enregistre la conception et historise SEULEMENT si elle a changé.

    « A changé » = l'empreinte DOCUMENT (:func:`empreinte_document`) de
    ``roof_layout`` diffère de celle du document déjà enregistré.

    Args:
        calepinage: le pivot (déjà enregistré).
        roof_layout: le document de conception (schéma v2, CAL232).
        user: l'auteur — posé côté serveur, jamais lu d'un corps de requête.
        libelle: libellé libre porté par la version créée.
        resultat / roof_image / version_moteur: mis à jour quand ils sont
            fournis ; ``None`` laisse la valeur en place.
        base_empreinte: ACAL22 — jeton d'écriture (en-tête ``If-Match``) :
            fourni, il est comparé SOUS VERROU DE LIGNE à l'empreinte
            « document » stockée ; différent ⇒ :class:`DocumentModifie`.
            ``None`` (défaut, tous les écrivains serveur) : aucune
            comparaison.
        valider_factures: ACAL1927 — ``True`` pour un document fourni par un
            client : ``consumption.factures_mois`` est validé (400 nommé).

    Returns:
        ``{'calepinage', 'version', 'layout_hash', 'inchange',
        'empreinte_document'}`` —
        ``version`` vaut ``None`` quand rien n'a changé, et ``inchange`` est
        alors ``True``.

    Raises:
        LayoutRefuse: pivot non enregistré, ou document de conception qui
            n'est pas un objet.
    """
    from django.db import transaction

    from apps.ventes.services import layout_hash

    from .versions import enregistrer_version

    if calepinage is None or not getattr(calepinage, 'pk', None):
        raise LayoutRefuse(
            "Le calepinage n'est pas encore enregistré : impossible d'y "
            "enregistrer une conception.", champ='calepinage')
    if roof_layout is not None and not isinstance(roof_layout, dict):
        raise LayoutRefuse(
            "La conception doit être un objet "
            f"(reçu : {type(roof_layout).__name__}).", champ='roof_layout')
    # ERR-ENF11-FUZZ-CALEPINAGE - U+0000 ou un demi-substitut isole (texte OU
    # cle) ne se range pas en JSONB : l'INSERT echouait en 500. Refus NOMME.
    from .parametres import _chemin_caractere_interdit

    chemin_interdit = _chemin_caractere_interdit(roof_layout, 'roof_layout')
    if chemin_interdit:
        raise LayoutCaractereInterdit(
            "« %s » contient un caractere interdit (caractere nul ou "
            "illisible) : corrigez la saisie." % chemin_interdit,
            champ='roof_layout')

    # CAL207 — miroir de la règle ventes/sync-layout : un calepinage dont le
    # devis lié a été envoyé est en lecture seule (409), sauf déverrouillage
    # explicite. La restauration de version (CAL20) passe par ICI, donc elle
    # hérite du même refus sans code dupliqué (CAL203).
    from .verrou import verifier_ecriture_autorisee

    verifier_ecriture_autorisee(calepinage)

    if valider_factures:
        # ACAL1927 — document venu d'un CLIENT (``POST layout/``) : mêmes règles que l'import, APRÈS
        # le refus d'état CAL207 (409) ; jamais pour une re-sauvegarde interne d'un document déjà stocké.
        from .io_layout import ImportLayoutRefuse, valider_factures_mois

        try:
            valider_factures_mois(roof_layout)
        except ImportLayoutRefuse as refus:
            raise LayoutRefuse(str(refus), champ=refus.champ) from refus

    champs = ['roof_layout', 'layout_hash', 'updated_at']
    with transaction.atomic():
        if base_empreinte is not None:
            # ACAL22 — le jeton est comparé au document STOCKÉ relu sous
            # verrou de ligne (jamais l'instance en mémoire, jamais
            # layout_hash) ; périmé ⇒ DocumentModifie, rien n'est écrit.
            calepinage.roof_layout = _relire_sous_verrou(calepinage,
                                                         base_empreinte)
        ancien_layout = calepinage.roof_layout
        # ERR-ACAL351 — un nombre inchangé garde son type stocké (15.0 / 15).
        roof_layout = garder_types_numeriques(ancien_layout, roof_layout)
        nouvelle = layout_hash(roof_layout) or ''
        # ACAL76 — un contour NOUVELLEMENT croisé (nœud papillon) est refusé
        # en nommant son chemin ; rien n'est écrit.
        _refuser_contour_nouvellement_croise(ancien_layout, roof_layout)
        # ACAL312 — une nature de zone NOUVELLEMENT inconnue est refusée en
        # nommant ``exclusionZones.<i>.nature`` ; rien n'est écrit.
        _refuser_nature_nouvellement_inconnue(ancien_layout, roof_layout)
        # ACAL39 — « inchangé » se décide sur l'empreinte DOCUMENT de
        # l'ancien document relu, jamais sur layout_hash (empreinte imprimée,
        # aveugle à l'horizon, aux champs au sol, à l'épingle…).
        inchange = (empreinte_document(ancien_layout)
                    == empreinte_document(roof_layout))
        if inchange and roof_layout is not None:
            # Un calepinage NÉ avec un document (copie d'un devis, d'un
            # modèle) n'a encore aucune version : le premier enregistrement
            # la dépose.
            from .versions import derniere_version

            inchange = derniere_version(calepinage) is not None

        calepinage.roof_layout = roof_layout
        calepinage.layout_hash = nouvelle
        if resultat is not None:
            calepinage.resultat = resultat
            champs.append('resultat')
        if roof_image is not None:
            calepinage.roof_image = roof_image or ''
            champs.append('roof_image')
        if version_moteur is not None:
            calepinage.version_moteur = version_moteur or ''
            champs.append('version_moteur')
        if user is not None and getattr(calepinage, 'etat_conception', '') == 'rapide':
            # ACAL1006 — une PERSONNE enregistre : vérifié, jamais l'inverse.
            calepinage.etat_conception = 'complet'
            champs.append('etat_conception')
        calepinage.save(update_fields=champs)

        version = None
        if not inchange:
            # ACAL45 — une version de GÉOMÉTRIE ne gèle plus le résultat
            # (calculé sur l'ANCIENNE conception) : ``resultat=None``.
            version = enregistrer_version(calepinage, user=user,
                                          libelle=libelle, resultat=None)
            if version is not None:
                # ACAL287 — la borne SAISIE par la société
                # (``presets.versions_conservees``) s'applique ICI, dans la
                # même transaction ; absente ⇒ rien n'est retiré (OFF).
                from .versions import purger_versions

                purger_versions(calepinage)
            # ACON25 (D-ACAL-2) — la variante RETENUE suit la conception ; son
            # résultat est périmé (ACAL112). Même document (retenir) ⇒ intacte.
            from django.utils import timezone

            from ..models import CalepinageVariante

            retenue = (CalepinageVariante.objects.select_for_update()
                       .filter(calepinage_id=calepinage.pk, retenue=True)
                       .first())
            if retenue is not None and (empreinte_document(retenue.roof_layout)
                                        != empreinte_document(roof_layout)):
                CalepinageVariante.objects.filter(pk=retenue.pk).update(
                    roof_layout=roof_layout, layout_hash=nouvelle,
                    resultat=None, updated_at=timezone.now())
            # D-ACAL-169 — l'entrée électrique suit le module POSÉ, et le dit.
            from .suivi_module_pose import suivre_le_module_pose

            suivre_le_module_pose(calepinage, roof_layout, user=user)

    if not inchange:
        # CAL26 — un enregistrement SIGNIFICATIF se journalise ; un renvoi à
        # l'identique n'est pas un événement (il ne s'est rien passé).
        from .journal import journaliser_layout

        journaliser_layout(calepinage, ancien_layout=ancien_layout,
                           nouveau_layout=roof_layout, user=user)

    # CAL128 — le verdict onduleur est REJOUÉ à chaque enregistrement de
    # conception : sans cela, on pourrait dessiner un champ que l'onduleur ne
    # peut pas recevoir en sautant simplement l'écran qui avertit. Le rejeu
    # n'écrit AUCUN statut (le blocage vit dans ``garde_publication``) et ne
    # lève jamais — une conception enregistrée ne se perd pas parce que son
    # verdict a bronché.
    from .electrique import rejouer_apres_layout

    rejouer_apres_layout(calepinage, user=user)
    if not inchange:
        simuler_apres_enregistrement(calepinage, user)
        _emettre_pose_enregistree(calepinage, nouvelle)
    return {
        'calepinage': calepinage,
        'version': version,
        'layout_hash': nouvelle,
        'inchange': inchange,
        # ACAL22 — le jeton de la PROCHAINE écriture (If-Match / base).
        'empreinte_document': empreinte_document(roof_layout),
    }


def _emettre_pose_enregistree(calepinage, empreinte_pose):
    """ACAL2011 (D-ACAL-97) — une pose dont l'empreinte a CHANGÉ le dit au
    moteur unique : ``pose_enregistree`` part UNE fois, après validation de la
    transaction (``inchange`` ne passe jamais ici). Un calepinage sans lead
    porte ``lead_id=None``. Best-effort : un abonné en échec ne casse jamais
    l'enregistrement."""
    import logging

    from django.db import transaction

    company_id, calepinage_id = calepinage.company_id, calepinage.pk
    lead_id = calepinage.lead_id

    def _emettre():
        for _recepteur, erreur in pose_enregistree.send_robust(
                sender='calepinage.Calepinage', company_id=company_id,
                calepinage_id=calepinage_id, lead_id=lead_id,
                empreinte_pose=empreinte_pose):
            if isinstance(erreur, Exception):
                logging.getLogger(__name__).warning(
                    'ACAL2011 : abonné de pose_enregistree en échec '
                    '(calepinage #%s)', calepinage_id, exc_info=erreur)

    transaction.on_commit(_emettre)


def simuler_apres_enregistrement(calepinage, user):
    """ACAL1987 (D-ACAL-90 renversée) — une pose ENREGISTRÉE (conception qui a
    CHANGÉ, ici ; matériel électrique désigné, ``electrique.enregistrer_entree``)
    part en simulation d'elle-même, une fois la transaction validée : le
    calepinage est relu en base (la conception enregistrée, jamais l'instance en
    mémoire) et ``services/simulation_auto`` décide (pose complète ? déjà
    simulée ? déjà en file ?). Sans auteur, rien : le job exige un utilisateur."""
    if calepinage is None or user is None:
        return
    from django.db import transaction

    pk = calepinage.pk

    def _lancer():
        from ..models import Calepinage
        from .simulation_auto import lancer_simulation_automatique

        relu = Calepinage.objects.filter(pk=pk).first()
        lancer_simulation_automatique(relu or calepinage, user=user)

    transaction.on_commit(_lancer)


def moteur_simule_la_pose():
    """ACAL2019 (D-ACAL-97) — le moteur unique simule-t-il la pose ? (niveau de règles
    courant ≥ 15, lu par la porte ``ventes.services``) : alors le bouton et
    l'enregistrement relancent le MOTEUR, jamais la simulation directe."""
    from apps.ventes.services import moteur_simule_la_pose as ouverte

    return ouverte()


def relancer_le_moteur(calepinage, *, user):
    """ACAL2019 — le bouton « Relancer » au niveau 15 : LA relance FORCÉE du moteur unique
    pour ce calepinage (porteur : son lead, sinon lui-même), qui exécute la simulation de la
    pose (ADEV149) et range sa version. Rend la ``Relance`` du moteur."""
    from types import SimpleNamespace

    from apps.ventes.services import relancer

    empreinte = getattr(calepinage, 'layout_hash', '') or ''
    toit = SimpleNamespace(empreinte=empreinte, plafond_panneaux=None) if empreinte else None
    return relancer(None, company=calepinage.company, declencheur={'origine': 'manuel', 'champs': []},
                    auteur=user, forcer=True, toit=toit, calepinage_id=calepinage.pk)
