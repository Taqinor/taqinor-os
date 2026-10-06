"""Géométrie du toit — layout, empreinte, calepinage, contour client.

Ce qui parle de FORMES et de SURFACES : lecture du layout 3D
(`extract_roof_config`, orientations et azimuts), son empreinte
(`layout_hash`), la pré-vérification d'une composition contre un layout,
le moteur de calepinage AOF164 (drapeau, zone villa, panneau retenu, compte
du moteur et arbitrage avec la tolérance) et le contour tracé par le client
(aire, plafond physique, zone de toit déduite).

QJR72 (M3) — DÉPLACEMENT PUR depuis ``apps/ventes/services.py``. Les corps
sont recopiés à l'identique ; la SEULE retouche est mécanique et obligatoire :
un corps descendu d'un cran (`apps/ventes/` → `apps/ventes/domain/`) voit son
point de départ relatif descendre avec lui, donc `from .x import y` devient
`from ..x import y` — MÊME cible (`apps.ventes.x`), au caractère près.

ORDRE DE CHARGEMENT (voir ``domain/bordereau.py``) : ``services.py`` importe
``domain/`` à la toute fin ; un module de ``domain/`` importe en BAS de fichier
les noms qu'il lit ailleurs. Quel que soit le module chargé le premier, chaque
attribut lu à l'import existe déjà.

NOM DU LOGGER FIGÉ sur ``apps.ventes.services`` : des tests capturent ce nom
précis (``assertLogs('apps.ventes.services')``). Un déplacement pur ne change
pas le nom sous lequel une ligne de journal est émise.
"""
import logging
import math
from collections import namedtuple

logger = logging.getLogger("apps.ventes.services")


def _aspect_to_orientation(aspect):
    """FG248 — azimut PVGIS (0=Sud, -90=Est, 90=Ouest, ±180=Nord) → libellé FR.

    Miroir inverse de ``orientationToAspect`` (apps/web/src/lib/roof.ts) pour que
    le devis affiche la même orientation que l'outil 3D. Aspect inconnu → ''."""
    try:
        a = float(aspect)
    except (TypeError, ValueError):
        return ''
    # Normalise dans [-180, 180].
    a = (a + 180.0) % 360.0 - 180.0
    table = [
        (0.0, 'Sud'), (-45.0, 'Sud-Est'), (45.0, 'Sud-Ouest'),
        (-90.0, 'Est'), (90.0, 'Ouest'),
        (-135.0, 'Nord-Est'), (135.0, 'Nord-Ouest'),
        (180.0, 'Nord'), (-180.0, 'Nord'),
    ]
    return min(table, key=lambda t: abs(a - t[0]))[1]


def _azimut_boussole_vers_aspect(azimut):
    """Azimut BOUSSOLE du builder (180 = Sud) → azimut PVGIS (0 = Sud).

    MÊME convention que le builder lui-même (``roofPro11/prodWindow.ts`` :
    ``aspect: res.facingAzimuthDeg - 180``), dans ]−180, 180] : le Nord vaut
    +180 (ACAL281). Valeur illisible → ``None`` (le libellé est alors omis,
    jamais deviné). ACAL281 : délègue à ``core.calepinage.geo`` (source
    unique de la conversion).
    """
    from core.calepinage.geo import boussole_vers_aspect

    return boussole_vers_aspect(azimut)


def _aspect_vers_azimut_boussole(aspect):
    """Azimut PVGIS (0 = Sud) → azimut BOUSSOLE (180 = Sud), dans [0, 360).

    Réciproque de :func:`_azimut_boussole_vers_aspect`. Elle existe pour que
    ``_pans_geometry['azimut_deg']`` n'ait qu'UN SEUL repère quelle que soit la
    clé source du layout (F3) — voir :func:`extract_roof_config`. Valeur
    illisible → ``None``. ACAL281 : délègue à ``core.calepinage.geo``.
    """
    from core.calepinage.geo import aspect_vers_boussole

    return aspect_vers_boussole(aspect)


def orientation_du_pan(zone):
    """ACAL58 — l'orientation d'un pan : celle des modules POSÉS d'abord.

    Un toit plat (``pitchDeg: 0``) porte des tables inclinées : la pente du
    TOIT n'est pas celle des MODULES. Le bloc ``geometry`` de la zone (WJ24 :
    ``tiltDeg``/``azimuthDeg``, azimut BOUSSOLE) décrit ce qui est réellement
    posé ; il prime donc, champ par champ, sur ``pitchDeg``/``pitch`` et
    ``facingAzimuthDeg``/``aspect``. Sans ``geometry`` (ou sans ses angles),
    la lecture du TOIT reste celle d'avant, au bit près.

    EXCEPTION ASSUMÉE : une pose est-ouest (``geometry.family == 'eastwest'``)
    porte DEUX faces ; son orientation n'est pas tranchée ici (C-ACAL-081) et
    garde la lecture du toit.

    Renvoie ``{inclinaison_deg, azimut_deg (boussole, 180 = Sud),
    aspect_pvgis (0 = Sud), source_orientation ('pose' | 'toit')}`` — jamais
    d'exception ; une valeur illisible reste ``None``.
    """
    zone = zone if isinstance(zone, dict) else {}
    geo = zone.get('geometry')
    if not isinstance(geo, dict) or geo.get('family') == 'eastwest':
        geo = {}

    # Lecture du TOIT (historique, F3 : azimut publié en BOUSSOLE).
    brut = zone.get('facingAzimuthDeg')
    if brut is not None:
        azimut_boussole = brut
        aspect_pvgis = _azimut_boussole_vers_aspect(brut)
    else:
        aspect_pvgis = zone.get('aspect')
        azimut_boussole = _aspect_vers_azimut_boussole(aspect_pvgis)
    pitch = zone.get('pitchDeg')
    if pitch is None:
        pitch = zone.get('pitch')

    source = 'toit'
    if geo.get('tiltDeg') is not None:
        pitch = geo.get('tiltDeg')
        source = 'pose'
    if geo.get('azimuthDeg') is not None:
        azimut_boussole = geo.get('azimuthDeg')
        aspect_pvgis = _azimut_boussole_vers_aspect(azimut_boussole)
        source = 'pose'
    return {
        'inclinaison_deg': pitch,
        'azimut_deg': azimut_boussole,
        'aspect_pvgis': aspect_pvgis,
        'source_orientation': source,
    }


def extract_roof_config(layout):
    """FG248 — extrait la config TOITURE d'un layout 3D (roofPro11) en un dict
    plat, JSON-sérialisable, indépendant de la version de l'outil.

    Lit les PANS de toiture (``areas``/``zones``/``pans``) — chacun portant
    ``roofType``, ``pitchDeg``/``pitch``, ``facingAzimuthDeg``/``aspect`` et un
    ``result`` ``{count, kwc, areaM2}`` (PV14 : à défaut, le bloc ``geometry``
    par pan de la sérialisation v1) — et en agrège :

        {surface_m2, nb_pans, nb_panneaux, kwc, orientation_principale,
         azimut_deg, inclinaison_deg, pans: [{...}]}

    Tolérant : entrées manquantes → champs omis ; aucune exception. Renvoie {}
    si le layout ne contient aucune géométrie de toiture exploitable (pour ne
    rien changer au comportement historique du seul bloc ``result``).
    """
    layout = layout or {}
    areas = (layout.get('areas') or layout.get('zones')
             or layout.get('pans') or [])
    if not isinstance(areas, list) or not areas:
        return {}

    pans = []
    total_surface = 0.0
    total_panels = 0
    total_kwc = 0.0
    best = None  # pan le plus puissant → orientation principale
    for a in areas:
        if not isinstance(a, dict):
            continue
        res = a.get('result') or {}
        # PV14 — les layouts DÉJÀ STOCKÉS (sérialisation roofPro11 v1) ne
        # portent PAS de bloc ``result`` par pan : la puissance et le compte
        # RÉELS y vivent dans le bloc ``geometry`` de la zone (WJ24 :
        # {azimuthDeg, tiltDeg, family, flush, kwc, count, origin, panels}).
        # Sans cette lecture un tel blob remontait 0 kWc — et le devis
        # reconstruit perdait le wattage panneau (aucun watt déductible, donc
        # plus de choix de produit à wattage exact). L'ordre est STRICT :
        # ``result`` d'abord (comportement historique inchangé au bit près),
        # ``geometry`` ensuite. ACAL59 (C-ACAL-118) — ``neededPanels`` (le
        # compte SOUHAITÉ, jamais le compte POSÉ) n'est PLUS un repli : un pan
        # non pavé compte 0.
        geo = a.get('geometry')
        if not isinstance(geo, dict):
            geo = {}
        count = int(res.get('count') or geo.get('count') or 0)
        kwc = float(res.get('kwc') or geo.get('kwc') or 0.0)
        # ACAL276 — un pan dessiné sans ``result`` a l'aire de ses sommets.
        surface = float(aire_du_pan(a) or 0.0)
        # ── DEUX CONVENTIONS D'ANGLE, ET ELLES SONT OPPOSÉES ────────────────
        # ``facingAzimuthDeg`` est l'AZIMUT BOUSSOLE du builder (180 = Sud) —
        # c'est ce que ``newAreaRecord()`` pose par défaut et ce que le solveur
        # d'orientation écrit ; le builder lui-même le convertit pour PVGIS en
        # retranchant 180 (``roofPro11/prodWindow.ts`` : « jambe sud : aspect =
        # azimut − 180 »).
        # ``aspect``, lui, est DÉJÀ l'azimut PVGIS (0 = Sud), et c'est cette
        # convention-là qu'attend ``_aspect_to_orientation``.
        #
        # Les deux entraient ici SANS conversion : un pan plein Sud
        # (``facingAzimuthDeg: 180``) ressortait donc « Nord », et l'annexe
        # « paramètres du site » de la proposition CLIENT publiait
        # ``orientation_deg: 180`` juste à côté de ``orientation: 'Nord'`` —
        # deux affirmations contradictoires, dont une fausse, sous les yeux du
        # client. On convertit désormais à la lecture, à l'endroit exact où la
        # convention est connue. ``azimut_deg`` reste la valeur BRUTE (aucun
        # autre consommateur ne change de repère) : seul le LIBELLÉ est corrigé.
        #
        # F3 — ET ``azimut_deg`` NE PUBLIE QU'UN SEUL REPÈRE. Il recopiait la
        # valeur BRUTE de la clé source : COMPASS venant de ``facingAzimuthDeg``,
        # PVGIS venant de ``aspect``. Deux toits plein Sud pouvaient donc sortir
        # d'ici avec ``azimut_deg`` 180 pour l'un et 0 pour l'autre, tous deux
        # étiquetés « Sud » — et ses consommateurs (annexe client, étude
        # bancable) n'avaient aucun moyen de savoir lequel ils lisaient. Le
        # repère PUBLIÉ est désormais la BOUSSOLE, toujours : la branche
        # ``facingAzimuthDeg`` garde sa valeur brute (aucun consommateur ne
        # change de repère), la branche ``aspect`` est convertie.
        #
        # ACAL58 — l'orientation POSÉE d'abord : voir :func:`orientation_du_pan`
        # (seule lecture de l'orientation côté ventes).
        orientation = orientation_du_pan(a)
        azimut_boussole = orientation['azimut_deg']
        aspect_pvgis = orientation['aspect_pvgis']
        pitch = orientation['inclinaison_deg']
        pan = {
            'label': a.get('label') or '',
            'roof_type': a.get('roofType') or '',
            'nb_panneaux': count,
            'kwc': round(kwc, 3) if kwc else 0.0,
            'surface_m2': round(surface, 2) if surface else 0.0,
            # BOUSSOLE (180 = Sud), toujours — voir F3 ci-dessus. Tout lecteur
            # qui a besoin de l'aspect PVGIS convertit lui-même, avec
            # ``_azimut_boussole_vers_aspect``.
            'azimut_deg': azimut_boussole,
            'inclinaison_deg': pitch,
            'orientation': _aspect_to_orientation(aspect_pvgis),
            # ACAL58 — 'pose' (tables posées, geometry) ou 'toit' (pente et
            # face du toit). Clé interne additive de ``_pans_geometry``.
            'source_orientation': orientation['source_orientation'],
        }
        pans.append(pan)
        total_surface += surface
        total_panels += count
        total_kwc += kwc
        if best is None or kwc > best['kwc']:
            best = pan

    if not pans:
        return {}

    cfg = {
        'surface_m2': round(total_surface, 2),
        'nb_pans': len(pans),
        'nb_panneaux': total_panels,
        'kwc': round(total_kwc, 3),
        'pans': pans,
    }
    if best is not None:
        cfg['orientation_principale'] = best['orientation']
        cfg['azimut_deg'] = best['azimut_deg']
        cfg['inclinaison_deg'] = best['inclinaison_deg']
    return cfg


#: ACAL40 (D-ACAL-4 + D-ACAL-21) — les clés de l'empreinte « IMPRIMÉE » :
#: tout ce qui change un chiffre que le client voit. ``a|b`` = alias lus dans
#: cet ordre. Les six premières entrées sont le canonique HISTORIQUE (QJ17),
#: toujours présent ; les suivantes n'entrent que PRÉSENTES et NON VIDES
#: (R3) — un document qui ne les porte pas garde son empreinte à l'octet.
#: Les obstacles d'ombrage d'un pan (``zones[].obstacles``, ``hauteurM``
#: compris) entrent avec le pan lui-même.
CLES_IMPRIMEES = (
    'zones|areas|pans',
    'result',
    'scenario',
    'panelWatt|watt',
    'battery',
    'poseSurfaces',
    'exclusionZones',
    'modules',
    'shading12x24',
    'environment',
    'shadeObstructions',
    'horizonProfile',
    # CIQ112 — le mode de pose DÉCLARÉ (toit du lead) choisit la règle de
    # pose des pans qui n'ont pas le leur : il change le calepinage chiffré.
    'modePoseDeclare',
)

#: Les clés ajoutées par ACAL40 — hors canonique historique, présentes et non
#: vides seulement.
_CLES_IMPRIMEES_AJOUTEES = CLES_IMPRIMEES[5:]


def _vide(valeur):
    return valeur is None or valeur in ('', [], {})


def layout_hash(layout):
    """L'empreinte « IMPRIMÉE » d'une conception (D-ACAL-4 + D-ACAL-21) :
    SHA-256 déterministe des seules :data:`CLES_IMPRIMEES`.

    Trois usages, une seule fonction :

    * **péremption** — un devis porte l'empreinte de la conception qu'il
      chiffre ; le badge « à jour » de la fiche (``selectors.calepinage_du_devis``)
      et ``layout_stale`` comparent les deux empreintes ;
    * **dédup** — ``from-layout`` et ``devis_brouillon_pour_layout`` (QJ17)
      rendent le brouillon existant d'un lead à la même empreinte (double clic,
      renvoi réseau) ;
    * **trace « corrigé après envoi »** — une resynchronisation d'un devis
      ENVOYÉ dont l'empreinte a bougé est une correction tracée (D-ACAL-21 :
      une retouche d'ombrage ou d'horizon en est une).

    L'état d'écran (``pin``, ``outline``, ``billKwh``, ``activeAreaId``,
    ``scene``…) n'y entre jamais : il est versionné par l'empreinte
    « document » du calepinage (``apps.calepinage.services.layout``), pas
    imprimé.
    """
    import hashlib
    import json as _json

    if not isinstance(layout, dict):
        return ''
    canonical = {
        'zones': layout.get('zones') or layout.get('areas') or layout.get('pans'),
        'result': layout.get('result'),
        'scenario': layout.get('scenario'),
        'panelWatt': layout.get('panelWatt') or layout.get('watt'),
        'battery': bool(layout.get('battery')),
    }
    for cle in _CLES_IMPRIMEES_AJOUTEES:
        valeur = layout.get(cle)
        if not _vide(valeur):
            canonical[cle] = valeur
    blob = _json.dumps(canonical, sort_keys=True, separators=(',', ':'),
                       default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


def battery_du_document(layout):
    """ACAL86 (C-ACAL-100) — LE lecteur de ``battery`` d'un document de pose,
    au format du contrat ``roof_layout_v2`` : objet NON VIDE ou ``None``.

    Les documents HISTORIQUES stockés avec un booléen sont normalisés À LA
    LECTURE (défaut gravé : aucune migration, aucun document réécrit) :
    ``True`` → ``{'declaree': True}`` (une batterie déclarée, capacité
    inconnue — aucune valeur de kWh n'est inventée), ``False``/absent/vide →
    ``None``, objet non vide → une COPIE de l'objet. ``layout_hash`` n'est pas
    concerné : il lit ``bool(battery)``, identique avant et après."""
    import copy as _copy

    if not isinstance(layout, dict):
        return None
    valeur = layout.get('battery')
    if isinstance(valeur, bool):
        return {'declaree': True} if valeur else None
    if isinstance(valeur, dict) and valeur:
        return _copy.deepcopy(valeur)
    return None


def poser_layout_hash(devis, empreinte):
    """CAL24 — pose l'empreinte du calepinage sur un devis, et RIEN d'autre.

    ``build_devis_from_layout`` ne l'écrit pas : le chemin 3D des ventes la
    posait lui-même juste après la création (``Devis.objects.filter(pk=…)
    .update(layout_hash=…)``), inline dans sa vue. Tout autre créateur — le
    module Calepinage en premier — aurait dû recopier cette écriture, donc la
    faire dériver. Elle vit maintenant ICI, en un seul endroit.

    C'est une écriture MINIMALE et sans effet de bord : `update()` ciblé, aucun
    statut touché (règle #4), aucun signal de sauvegarde déclenché.
    """
    from apps.ventes.models import Devis

    if devis is None or not getattr(devis, 'pk', None) or not empreinte:
        return devis
    Devis.objects.filter(pk=devis.pk).update(layout_hash=empreinte)
    devis.layout_hash = empreinte
    return devis


def scenario_du_layout(layout):
    """QJR82 — le scénario du pipeline (``'sans'``/``'avec'``/``'les_deux'``)
    lu dans un layout 3D.

    MÊME lecture que ``build_devis_from_layout`` — mots-clés « batterie » /
    « hybride » dans ``scenario``, ou la clé ``battery`` — plus le libellé
    ``'les_deux'`` que le calepinage sait désormais porter. Layout muet ⇒
    ``'sans'``, le défaut résidentiel d'hier, à l'octet près.
    """
    brut = str((layout or {}).get('scenario') or '').lower()
    if brut in (COMPOSITION_LES_DEUX, 'les deux', 'les-deux'):
        return COMPOSITION_LES_DEUX
    if ('batterie' in brut or 'hybride' in brut
            or bool((layout or {}).get('battery'))):
        return COMPOSITION_AVEC
    return COMPOSITION_SANS


#: QJR165 — CE QU'UN LAYOUT DIT, RENDU EN UN SEUL OBJET.
#:
#: DEUX WATTAGES, ET LA NUANCE EST LOAD-BEARING :
#:
#: * ``watt`` est le wattage à COMPOSER. Il n'est JAMAIS ``None`` : à défaut de
#:   tout, c'est le repli ``lignes.LAYOUT_WATT_REPLI``, et la composition
#:   applique de toute façon ce même repli en aval
#:   (``composition_residentielle``) ;
#: * ``watt_declare`` est le wattage que le layout DÉCLARE, ou qu'il laisse
#:   DÉDUIRE de son kWc — et il vaut ``None`` quand il n'y a rien à déduire.
#:   La sélection catalogue a besoin de cette nuance : « aucun wattage cible »
#:   (aucune préférence, tout panneau tarifé convient) n'est PAS « 550 W »
#:   (préférer le 550). Confondre les deux, c'est épingler un panneau que
#:   personne n'a demandé.
#:
#: ``toiture`` est rendue avec le reste pour qu'un appelant qui en a besoin
#: (``_calepinage_range``, le journal) ne rejoue pas ``extract_roof_config``.
LectureLayout = namedtuple(
    'LectureLayout',
    'compte watt watt_declare kwc scenario toiture pans modeles')


def _nombre_fini(valeur):
    """``float`` fini et positif, ou ``None`` — jamais une valeur supposée."""
    try:
        v = float(valeur)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) and v > 0 else None


#: ACAL59 — les genres de surface de pose (``roof_layout_v2``,
#: ``poseSurfaces[].kind``). Un pan de toit est ``'toit'``.
KINDS_SURFACE = ('sol', 'ombriere', 'facade')


def _entier_pose(valeur):
    """Un compte POSÉ lisible (entier ≥ 0), ou ``None`` s'il est absent."""
    if valeur is None:
        return None
    try:
        v = float(valeur)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(v) or v < 0:
        return None
    return int(round(v))


def pans_du_document(layout):
    """ACAL59 (C-ACAL-035, C-ACAL-118, D-ACAL-5) — LA primitive PURE : les
    pans d'un document de pose, toit ET surfaces de pose (champ au sol,
    ombrière, façade — chacune est un pan à part entière).

    Rend ``[{cle, kind, libelle, modules, kwc, inclinaison_deg, azimut_deg,
    source}]`` (+ ``avertissement`` pour un pan non pavé, + ``refus`` pour
    une surface dont le module n'a pas de puissance). Ne lève jamais : le
    refus est PORTÉ, et c'est la composition (pré-vol
    :func:`validate_composition_for_layout`) qui le prononce — un document
    déjà enregistré n'est jamais rendu illisible.

    * pan de TOIT (``zones``/``areas``/``pans``) — compte POSÉ, par
      préséance : ``len(geometry.panels)`` > ``geometry.count`` >
      ``result.count`` du pan (la zone synthétique de l'auto-devis, qui ne
      porte que ``result``, reste comptée). ``neededPanels`` n'est JAMAIS un
      compte posé : un pan non pavé vaut 0 module et le DIT
      (« pan <libellé> non pavé — non chiffré ») ;
    * SURFACE DE POSE (``poseSurfaces``) — ``engine.modules`` (recopié du
      moteur, jamais recalculé) ; kWc = modules × ``moduleWc`` ; azimut de
      FACE = ``rowAzimuthDeg`` + 90 (défaut gravé du contrat). Une surface
      pavée SANS ``moduleWc`` porte un ``refus`` NOMMANT la surface (jamais
      une puissance de repli).

    Le ``result`` RACINE n'est pas lu ici : c'est le toit seul, et
    :func:`lire_layout` ne le lit qu'à défaut de toute géométrie de zone.
    """
    layout = layout if isinstance(layout, dict) else {}
    pans = []
    watt_annonce = _nombre_fini(layout.get('panelWatt') or layout.get('watt'))
    catalogue = _catalogue_modules(layout)
    zones = (layout.get('zones') or layout.get('areas')
             or layout.get('pans') or [])
    for index, zone in enumerate(zones if isinstance(zones, list) else []):
        if not isinstance(zone, dict):
            continue
        geo = zone.get('geometry')
        geo = geo if isinstance(geo, dict) else {}
        res = zone.get('result')
        res = res if isinstance(res, dict) else {}
        libelle = str(zone.get('label') or zone.get('id')
                      or 'Pan %d' % (index + 1))
        if isinstance(geo.get('panels'), list):
            modules, source = len(geo['panels']), 'geometry.panels'
        elif _entier_pose(geo.get('count')) is not None:
            modules, source = _entier_pose(geo.get('count')), 'geometry.count'
        elif _entier_pose(res.get('count')) is not None:
            modules, source = _entier_pose(res.get('count')), 'result.count'
        else:
            modules, source = 0, 'aucune'
        # ACAL62 — le MODÈLE posé sur ce pan (``geometry.moduleId`` →
        # ``modules[]``). Un renvoi qui ne résout pas est un refus NOMMÉ
        # (même règle que ``io_layout._refuser_module_inconnu``), porté
        # par le pan et prononcé par la composition.
        module_id = geo.get('moduleId')
        modele = catalogue.get(module_id) if module_id is not None else None
        watt_pan = (_nombre_fini(modele.get('pmaxWc')) if modele else None)
        kwc = _nombre_fini(geo.get('kwc')) or _nombre_fini(res.get('kwc'))
        if kwc is None and modules and (watt_pan or watt_annonce):
            kwc = modules * (watt_pan or watt_annonce) / 1000.0
        orientation = orientation_du_pan(zone)
        pan = {
            'cle': str(zone.get('id') or 'zone-%d' % (index + 1)),
            'kind': 'toit',
            'libelle': libelle,
            'modules': modules,
            'kwc': round(kwc, 3) if (kwc and modules) else None,
            'inclinaison_deg': orientation['inclinaison_deg'],
            'azimut_deg': orientation['azimut_deg'],
            'source': source,
            'module_id': module_id,
            'produit_id': (modele or {}).get('produitId'),
            'module_wc': watt_pan,
        }
        if modules <= 0:
            pan['kwc'] = None
            pan['avertissement'] = 'pan %s non pavé — non chiffré' % libelle
        elif module_id is not None and modele is None:
            pan['refus_champ'] = 'zones.%d.geometry.moduleId' % index
            pan['refus'] = (
                "Pan « %s » : le module « %s » ne figure pas dans « modules » "
                "(modèles déclarés : %s)."
                % (libelle, module_id, ', '.join(sorted(catalogue)) or 'aucun'))
        pans.append(pan)

    surfaces = layout.get('poseSurfaces')
    for index, surface in enumerate(
            surfaces if isinstance(surfaces, list) else []):
        if not isinstance(surface, dict):
            continue
        moteur = surface.get('engine')
        moteur = moteur if isinstance(moteur, dict) else {}
        modules = _entier_pose(moteur.get('modules')) or 0
        watt = _nombre_fini(surface.get('moduleWc'))
        kind = surface.get('kind')
        kind = kind if kind in KINDS_SURFACE else 'sol'
        libelle = str(surface.get('label') or surface.get('id')
                      or 'Surface %d' % (index + 1))
        rangee = _nombre_fini(surface.get('rowAzimuthDeg'))
        if rangee is None and surface.get('rowAzimuthDeg') == 0:
            rangee = 0.0
        pan = {
            'cle': str(surface.get('id') or 'surface-%d' % (index + 1)),
            'kind': kind,
            'libelle': libelle,
            'modules': modules,
            'kwc': (round(modules * watt / 1000.0, 3)
                    if (modules and watt) else None),
            'inclinaison_deg': surface.get('tiltDeg'),
            'azimut_deg': ((rangee + 90.0) % 360.0
                           if rangee is not None else None),
            'source': 'engine.modules',
            'module_id': None,
            'produit_id': None,
            'module_wc': watt,
        }
        if modules <= 0:
            pan['avertissement'] = 'pan %s non pavé — non chiffré' % libelle
        elif watt is None:
            pan['refus_champ'] = 'poseSurfaces.%d.moduleWc' % index
            pan['refus'] = (
                "Surface de pose « %s » : la puissance du module (moduleWc) "
                "n'est pas renseignée — ses %d modules ne peuvent pas être "
                "chiffrés. Saisissez le module de la surface puis relancez."
                % (libelle, modules))
        pans.append(pan)
    return pans


def _catalogue_modules(layout):
    """``{id: entrée}`` des modèles déclarés dans ``modules[]`` (CALX82)."""
    catalogue = layout.get('modules') if isinstance(layout, dict) else None
    if not isinstance(catalogue, list):
        return {}
    return {entree['id']: entree for entree in catalogue
            if isinstance(entree, dict) and isinstance(entree.get('id'), str)}


def modeles_des_pans(layout, pans, *, compte, watt):
    """ACAL62 (C-ACAL-042) — les MODÈLES de module posés :
    ``[{produit_id, watt, count}]``, regroupés par (produit, puissance) dans
    l'ordre du document, comptes par pan issus de :func:`pans_du_document`
    (surfaces de pose comprises : leur modèle est leur ``moduleWc``).

    Un document SANS ``modules[]`` garde le comportement d'aujourd'hui au bit
    près : ``[{produit_id: None, watt: <watt lu>, count: <compte>}]``."""
    if not _catalogue_modules(layout):
        return [{'produit_id': None, 'watt': watt, 'count': compte}]
    groupes = {}
    for pan in pans or ():
        if pan.get('modules', 0) <= 0:
            continue
        puissance = pan.get('module_wc')
        cle = (pan.get('produit_id'),
               int(round(puissance)) if puissance else watt)
        groupes[cle] = groupes.get(cle, 0) + int(pan['modules'])
    if not groupes:
        return [{'produit_id': None, 'watt': watt, 'count': compte}]
    return [{'produit_id': produit, 'watt': puissance, 'count': nombre}
            for (produit, puissance), nombre in groupes.items()]


def modeles_designes(layout):
    """ACAL63 (C-ACAL-042) — les modèles POSÉS qui désignent une FICHE
    produit (``produit_id`` non nul), ou ``[]``. Un document sans fiche
    désignée garde la composition au wattage (``_pick_product``), au bit
    près ; dès qu'une fiche est désignée, la composition et la resynchro
    vendent UNE ligne panneau PAR MODÈLE (les modèles sans fiche y suivent la
    règle du wattage)."""
    if not isinstance(layout, dict):
        return []
    modeles = lire_layout(layout).modeles
    if not any(m.get('produit_id') for m in modeles):
        return []
    return [dict(m) for m in modeles if int(m['count'] or 0) > 0]


def refus_des_pans(pans):
    """ACAL59 — les refus NOMMÉS portés par :func:`pans_du_document` (une
    surface pavée sans puissance module), dans l'ordre du document."""
    return [p['refus'] for p in pans or () if p.get('refus')]


def lire_layout(layout, *, toiture=None, compte=None, kwc=None):
    """QJR165 — L'UNIQUE lecture d'un layout 3D : compte, watt, kWc, scénario.

    POURQUOI CETTE FONCTION EXISTE. Ce dépôt lisait le MÊME blob de deux
    façons : la resynchronisation par ``_cible_panneaux_du_layout`` /
    ``_watt_du_layout``, la création 3D par une lecture INLINE recopiée dans
    ``build_devis_from_layout``. Les deux chaînes de repli avaient divergé pour
    de bon — ``result.count`` accepté d'un seul côté, le forfait 550 W posé
    d'un seul côté, le wattage normalisé d'un seul côté, le scénario
    « les deux » compris d'un seul côté — si bien que le même toit pouvait
    ressortir avec deux comptes ou deux wattages selon le bouton par lequel le
    devis passait. Les quatre divergences ont été mesurées puis tranchées
    (QJR165) ; la chaîne tranchée est écrite ICI, et nulle part ailleurs.

    LA RÈGLE QUI GOUVERNE CHAQUE REPLI : **on n'invente jamais un compte**. Un
    nombre n'est retenu que s'il est PRÉSENT dans le blob (``result.panels``,
    ``result.count``) ou MESURÉ sur sa géométrie (la somme des pans, cf.
    ``extract_roof_config``). Rien ne comble un compte manquant : un layout
    muet rend 0, et l'étape de vérification refuse — jamais un compte forfait.

    ``toiture`` — la géométrie déjà extraite, quand l'appelant l'a. ``None``
    (le défaut) la calcule.

    ``compte`` / ``kwc`` — non ``None``, ils REMPLACENT ce que le layout
    annonce, et le wattage se déduit alors de ce couple-là. C'est ce dont le
    chemin de création a besoin après l'arbitrage AOF164 : le compte RETENU par
    le moteur devient la base de lecture, exactement comme avant.
    """
    layout = layout if isinstance(layout, dict) else {}
    if toiture is None:
        toiture = extract_roof_config(layout) or {}
    result = dict(layout.get('result') or {})

    # ── ACAL59 (C-ACAL-035, D-ACAL-5) — LA SOMME DES PANS POSÉS ────────────
    # Un site toit + champ au sol / ombrière est chiffré sur la SOMME des
    # modules posés (``pans_du_document``) : la surface de pose n'est plus un
    # repli quand le toit est muet, c'est un pan. Le ``result`` racine (le
    # toit seul, D-ACAL-5) n'est lu qu'à défaut de toute géométrie de zone —
    # jamais additionné aux zones (aucun double compte).
    pans = pans_du_document(layout)
    toit = [p for p in pans if p['kind'] == 'toit']
    surfaces = [p for p in pans if p['kind'] != 'toit']
    zones_mesurees = any(p['source'] != 'aucune' for p in toit)
    if compte is None:
        if zones_mesurees:
            compte_toit = sum(p['modules'] for p in toit)
        else:
            compte_toit = int(result.get('panels') or result.get('count')
                              or 0)
        compte = compte_toit + sum(p['modules'] for p in surfaces)
    else:
        compte = int(compte or 0)

    if kwc is None:
        toit_paves = [p for p in toit if p['modules'] > 0]
        if zones_mesurees and toit_paves and all(p['kwc']
                                                 for p in toit_paves):
            kwc_toit = sum(p['kwc'] for p in toit_paves)
        else:
            kwc_toit = float(result.get('kwc') or toiture.get('kwc') or 0.0)
        surfaces_pavees = [p for p in surfaces if p['modules'] > 0]
        if all(p['kwc'] for p in surfaces_pavees):
            kwc = kwc_toit + sum(p['kwc'] for p in surfaces_pavees)
        else:
            # Une surface pavée sans puissance module : aucun kWc inventé —
            # le wattage retombe sur la chaîne habituelle (la composition,
            # elle, refuse en nommant la surface).
            kwc = 0.0
        kwc = round(kwc, 3) if kwc else 0.0
    else:
        kwc = float(kwc or 0.0)

    # Le wattage ANNONCÉ d'abord (``panelWatt``, son alias historique
    # ``watt``), normalisé en entier — un blob peut porter « 545.6 » ou
    # « "550" », et le laisser filer tel quel jusqu'à ``float(panel_watt)``
    # faisait dépendre le panneau composé du TYPE JSON reçu (une chaîne
    # illisible y levait même une exception). Illisible ⇒ on l'ignore et on
    # déduit, exactement comme si le champ était absent.
    watt_declare = None
    annonce = layout.get('panelWatt') or layout.get('watt')
    if annonce:
        try:
            watt_declare = int(round(float(annonce)))
        except (TypeError, ValueError):
            watt_declare = None
    if watt_declare is None and kwc and compte:
        watt_declare = int(round(kwc * 1000 / compte / 10) * 10)

    watt = watt_declare if watt_declare is not None else LAYOUT_WATT_REPLI
    return LectureLayout(
        compte=compte,
        watt=watt,
        watt_declare=watt_declare,
        kwc=kwc,
        scenario=scenario_du_layout(layout),
        toiture=toiture,
        pans=pans,
        # ACAL62 — les modèles POSÉS (produit, watt, nombre), plus un seul
        # entier ``panelWatt`` : la composition (D08-T24) les lira.
        modeles=modeles_des_pans(layout, pans, compte=compte, watt=watt),
    )


def validate_composition_for_layout(layout, company, *, lead=None):
    """QJ17 — pre-flight composition check before building a devis.

    Returns ``None`` when the composition is valid.  Returns a list of French
    error strings when problems are detected (caller should surface them inline
    rather than raising a PDF error at render time).

    QJR82 — CE N'EST PLUS QU'UN ADAPTATEUR. Les règles et les messages vivent
    dans ``pipeline.verifier``, l'étape 4 du pipeline, que les autres origines
    (devis automatique, tunnel) appellent DIRECTEMENT. Cette fonction traduit
    simplement un LAYOUT en ``IntentionComposition`` et délègue : le chemin 3D
    garde donc, au caractère près, les messages qu'il prononçait — et le
    commercial lit désormais les mêmes, quel que soit le bouton.

    Deux gains de la généralisation : le layout peut déclarer ``'les_deux'``
    (l'étape exige alors les DEUX onduleurs ET la batterie — un devis à deux
    options ne peut plus partir en ne sachant servir qu'une moitié), et
    ``role``/``gamme`` descendent jusqu'à la sélection catalogue.

    Rules (aligned with quote_engine/builder.py keyword classification):
    - At least 1 panel is required.
    - A battery scenario requires both a hybrid inverter AND a battery in the
      catalogue (priced); if either is missing, warn the agent.
    - A réseau scenario requires a réseau/injection inverter (priced).
    - A price-less required product blocks the composition (never auto-quote it).

    ACAL32 (C-ACAL-105) — ``lead`` : le pré-vol compose avec la MÊME phase et
    le MÊME site isolé que la création (``taille.phase_et_isolement_du_lead``).
    Un site isolé que le catalogue ne sait pas servir (onduleur autonome /
    batterie) lève ``AutoDevisError(field='hors_reseau')`` — un refus NOMMÉ
    (422 ``{hors_reseau: …}``), pas une erreur de composition anonyme.
    """
    if not isinstance(layout, dict):
        return ['Layout invalide — impossible de valider la composition.']

    # QJR165 — LE LECTEUR UNIQUE. Ce pré-vol comptait les panneaux avec sa
    # propre chaîne de repli ; il compte désormais avec CELLE de la création
    # qu'il précède — sans quoi il pouvait refuser (« aucun panneau ») un
    # layout que la création aurait accepté, ou l'inverse.
    lecture = lire_layout(layout)
    from apps.ventes.domain.taille import (
        AutoDevisError, phase_et_isolement_du_lead)
    # ACAL59 (D-ACAL-5) — une surface pavée sans puissance module est
    # REFUSÉE en la nommant (422), jamais chiffrée à une puissance de repli.
    # ACAL62 — de même un pan qui désigne un module absent de ``modules[]``.
    refusants = [p for p in lecture.pans if p.get('refus')]
    if refusants:
        raise AutoDevisError(refusants[0]['refus'],
                             field=refusants[0].get('refus_champ')
                             or 'poseSurfaces')
    phase, hors_reseau = phase_et_isolement_du_lead(lead)

    # PVMRQ — pas de devis ici (pré-vol AVANT création) ⇒ pas de gamme connue :
    # ``marque_preferee`` retombe explicitement sur le slot Essentielle.
    # ``kwc`` n'est délibérément PAS transmis : la règle du calepinage est
    # « aucun panneau détecté », pas « aucune puissance » — un layout à 0
    # panneau doit être refusé même s'il porte encore un kWc d'une version
    # antérieure du tracé. C'est le comportement d'hier, mot pour mot.
    erreurs = verifier(IntentionComposition(
        company=company,
        nb_panneaux=lecture.compte,
        scenario=(COMPOSITION_AVEC if hors_reseau else lecture.scenario),
        phase=phase,
        hors_reseau=hors_reseau,
        # ACAL63 — un module DÉSIGNÉ non tarifé est refusé dès le pré-vol.
        modeles=modeles_designes(layout) or None,
    ))
    # « Aucun panneau » reste l'erreur de composition qu'elle a toujours été
    # (rien à servir, isolé ou non) ; seul le manque de catalogue autonome
    # est le refus NOMMÉ du site isolé.
    if hors_reseau and erreurs and erreurs[0] != MSG_AUCUN_PANNEAU:
        raise AutoDevisError(erreurs[0], field='hors_reseau')
    return erreurs


# ── AOF164 — bascule du calcul résidentiel sur le MOTEUR PARTAGÉ ────────────
#
# Le compte de panneaux du devis résidentiel vient aujourd'hui du cerveau
# TypeScript de roofPro11 (``layout['result']['panels']``). Le moteur
# ``core/calepinage`` sait faire le même travail, en exact et avec sa preuve —
# mais on ne remplace pas un calcul en production sur une intuition : la
# bascule vit derrière un DRAPEAU (défaut OFF) et se juge sur des écarts
# JOURNALISÉS, pas sur une conviction.
#
# Trois invariants tiennent cette tâche :
#   * drapeau OFF -> comportement BIT-IDENTIQUE (retour immédiat, avant tout
#     appel moteur et avant toute écriture de journal) ;
#   * un devis DÉJÀ ÉMIS n'est jamais recalculé (voir
#     ``apps.ventes.selectors.comparaison_calepinage_devis``) ;
#   * une panne du moteur ne fait JAMAIS échouer une création de devis : on
#     journalise et on garde le compte historique.
#
# Les mots-clés de classification (panneau / onduleur réseau|injection|hybride
# / batterie) ne bougent pas : ils sont le contrat d'alignement avec
# ``quote_engine/builder.py`` dont dépend le découpage des options du PDF
# (CLAUDE.md, règle #4). Cette tâche ne touche QUE le COMPTE.

#: Nom du drapeau — lu par ``getattr`` pour que l'ABSENCE du réglage vaille OFF.
DRAPEAU_MOTEUR_CALEPINAGE = 'USE_MOTEUR_CALEPINAGE'

# ── PVG2 — garde de TOLÉRANCE sur l'arbitrage A/B (décision fondateur) ───────
#
# La bascule AOF164 remplaçait le compte historique par celui du moteur DÈS que
# le drapeau était levé, quelle que soit l'ampleur de l'écart. Un moteur qui
# lit mal une géométrie (un pan sans obstacle déclaré, un contour ouvert, une
# unité inattendue) pouvait donc, silencieusement, faire passer une villa de 12
# à 40 panneaux — et le devis partait ainsi.
#
# Décision du fondateur : SÉCURITÉ PAR DÉFAUT. Un petit écart est une
# correction (le moteur est plus fin que le cerveau TypeScript, c'est le but de
# la bascule) ; un GRAND écart est une ANOMALIE, et devant une anomalie on
# garde le compte historique et on ALERTE — jamais un remplacement silencieux.
#
# Deux tolérances, satisfaites en OU (l'une suffit) : un écart de quelques
# modules est absolu (une villa de 12 panneaux tolère ±2), un écart relatif
# couvre les grandes toitures (200 modules tolèrent ±5 %, soit ±10).
#: Écart ABSOLU toléré, en nombre de modules.
TOLERANCE_ARBITRAGE_MODULES = 2
#: Écart RELATIF toléré, en % du compte historique.
TOLERANCE_ARBITRAGE_PCT = 5.0


def _ecart_dans_la_tolerance(ancien, ecart):
    """L'écart moteur↔historique reste-t-il dans la tolérance PVG2 ?

    Vrai dès qu'UNE des deux tolérances est satisfaite (modules OU pourcentage).
    Un compte historique nul ou négatif n'a pas de pourcentage qui ait un sens :
    seule la tolérance en modules s'applique alors (jamais une division par 0).
    """
    ecart_abs = abs(int(ecart))
    if ecart_abs <= TOLERANCE_ARBITRAGE_MODULES:
        return True
    if ancien > 0:
        return (ecart_abs * 100.0 / ancien) <= TOLERANCE_ARBITRAGE_PCT
    return False


def moteur_calepinage_actif():
    """Le drapeau de bascule est-il levé ? ABSENT = OFF (jamais l'inverse)."""
    from django.conf import settings

    return bool(getattr(settings, DRAPEAU_MOTEUR_CALEPINAGE, False))


def _zone_villa_depuis_pan(pan):
    """``AreaRecord`` roofPro11 -> ``AreaRecord`` attendu par l'adaptateur villa.

    roofPro11 sérialise ``vertices: LngLat[]`` (``[lng, lat]``) et des obstacles
    ``{centerLng, centerLat, lengthM (nord-sud), widthM (est-ouest)}``.
    L'adaptateur d'AOF162 attend ``polygon`` / ``center`` / ``widthM`` /
    ``heightM`` avec ``heightM`` = étendue NORD-SUD : la correspondance est
    faite ICI, explicitement, et jamais devinée ailleurs.

    Rend ``None`` quand le pan ne porte pas de contour exploitable — un layout
    sans géométrie n'est pas une erreur, c'est simplement un cas où le moteur
    n'a rien à dire.
    """
    if not isinstance(pan, dict):
        return None
    sommets = pan.get('vertices') or pan.get('polygon') or pan.get('points')
    if not isinstance(sommets, (list, tuple)) or len(sommets) < 3:
        return None

    obstacles = []
    for brut in (pan.get('obstacles') or ()):
        if not isinstance(brut, dict):
            continue
        lng = brut.get('centerLng')
        lat = brut.get('centerLat')
        if lng is None or lat is None:
            continue
        obstacles.append({
            'id': brut.get('id') or 'OBS',
            'center': [lng, lat],
            # widthM = est-ouest (axe x du moteur villa) ;
            # lengthM = nord-sud (axe y).
            'widthM': brut.get('widthM') or 1.0,
            'heightM': brut.get('lengthM') or brut.get('heightM') or 1.0,
        })

    type_toit = (pan.get('roofType') or '').lower()
    pente = pan.get('pitchDeg')
    if pente is None:
        pente = pan.get('pitch') or 0.0
    azimut = pan.get('facingAzimuthDeg')
    if azimut is None:
        azimut = pan.get('aspect')
    return {
        'id': str(pan.get('id') or pan.get('label') or 'ZONE'),
        'polygon': [list(p) for p in sommets],
        'flat': type_toit != 'pitched',
        'tilt': float(pente or 0.0),
        'azimuth': float(azimut if azimut is not None else 180.0),
        'obstacles': obstacles,
    }


def _produit_panneau_du_devis(devis):
    """PV42 — le produit PANNEAU d'un devis EXISTANT, ou ``None``.

    Première ligne classée « panneau » qui porte une fiche produit (une ligne
    libre n'a pas de géométrie à donner au calepinage). Même classification que
    partout ailleurs — la désignation d'abord, le nom du produit ensuite.
    """
    if devis is None:
        return None
    for ligne in _lignes_produit(devis):
        if not _classe_ligne(ligne, _is_panel):
            continue
        produit = getattr(ligne, 'produit', None)
        if produit is not None:
            return produit
    return None


def _produit_designe(company, produit_id):
    """ACAL63 — la fiche ``stock.Produit`` désignée, TARIFÉE, dans le
    catalogue de la société (``catalogue_de_la_societe`` : société ou global),
    ou ``None``. Lecture seule."""
    try:
        cible = int(produit_id)
    except (TypeError, ValueError):
        return None
    from apps.ventes.domain.catalogue import _has_price, catalogue_de_la_societe
    for produit in catalogue_de_la_societe(company):
        if getattr(produit, 'pk', None) == cible:
            return produit if _has_price(produit) else None
    return None


def _panneau_pour_calepinage(layout, *, company=None, devis=None):
    """PV42 — le PANNEAU sur lequel calepiner, et la société qui le scope.

    Deux sources, dans cet ordre : la ligne panneau du devis quand il en existe
    un (le module RÉELLEMENT vendu), sinon le catalogue de la société au
    wattage annoncé par le layout (``panelWatt``/``watt``, à défaut déduit du
    kWc) — la même sélection que celle qui composera les lignes du devis.

    Rend ``(produit, company_de_scoping)``. La société n'est rendue QUE si le
    produit lui appartient vraiment : un produit GLOBAL (``company`` nulle,
    catalogue partagé) passé avec une société ferait lever le garde-fou de
    ``kit_panneau_du_produit`` (« appartient à une autre société ») et on
    perdrait le kit réel pour rien. Aucun produit trouvé → ``(None, None)``,
    et le moteur retombe sur son kit villa par défaut.
    """
    produit = _produit_panneau_du_devis(devis)
    if produit is None and company is not None:
        # ACAL63 — le module DÉSIGNÉ par le calepinage (``modules[].
        # produitId``) passe devant le choix au wattage.
        for modele in modeles_designes(layout):
            designe = _produit_designe(company, modele.get('produit_id'))
            if designe is not None:
                produit = designe
                break
    if produit is None and company is not None:
        # QJR165 — LE LECTEUR UNIQUE, et sa forme ``watt_declare`` : ici
        # « aucun wattage déductible » doit rester ``None`` (aucune préférence
        # de wattage, tout panneau tarifé convient) et surtout PAS le forfait
        # 550 W, qui épinglerait un panneau que personne n'a demandé.
        watt = lire_layout(layout).watt_declare
        try:
            # PVMRQ — le devis (s'il en existe déjà un) donne sa gamme réelle ;
            # sans lui, ``marque_preferee`` retombe sur le slot Essentielle.
            produit = _pick_product(
                company, _is_panel, watt=watt, role='panneau',
                gamme=gamme_nom(devis) if devis is not None else None)
        except Exception:      # pragma: no cover - catalogue indisponible
            produit = None
    if produit is None:
        return None, None
    proprietaire = getattr(produit, 'company_id', None)
    if proprietaire is None:
        # Produit du catalogue GLOBAL : aucun scoping société à opposer.
        return produit, None
    return produit, company


def compte_moteur_du_layout(layout, *, company=None, devis=None):
    """Compte de modules rendu par le MOTEUR pour ce layout, ou ``None``.

    Somme les pans : chacun passe par
    ``apps.calepinage.selectors.calepinage_villa`` (lecture cross-app
    sanctionnée — jamais les modèles du module), qui délègue au moteur partagé
    d'AOF163. SOLMVP15b : ce moteur vivait dans ``apps/ao`` ; il a été
    rapatrié dans ``apps/calepinage/villa_service.py`` à la ligne près (mêmes
    signatures, même dict de sortie) pour qu'AO puisse sortir du produit sans
    perdre le recomptage. Aucune ligne n'est créée.

    PV42 — ``company``/``devis`` servent à résoudre le PANNEAU réellement vendu
    et à le passer en ``produit_panneau`` (PV12) : le calepinage est alors posé
    sur la géométrie de CE module, plus sur le kit villa générique. Sans
    panneau résoluble (ni devis, ni société, ni catalogue), l'appel est
    strictement celui d'hier.

    Rend ``None`` (et jamais une exception) dès que la géométrie manque ou que
    le moteur refuse : l'appelant garde alors le compte historique.
    """
    pans = ((layout or {}).get('areas') or (layout or {}).get('zones')
            or (layout or {}).get('pans') or [])
    if not isinstance(pans, list) or not pans:
        return None

    from apps.calepinage.selectors import calepinage_villa

    produit_panneau, societe_panneau = _panneau_pour_calepinage(
        layout, company=company, devis=devis)

    modules = 0
    detail = []
    for pan in pans:
        zone = _zone_villa_depuis_pan(pan)
        if zone is None:
            continue
        try:
            sortie = calepinage_villa(zone, ordre='lnglat',
                                      produit_panneau=produit_panneau,
                                      company=societe_panneau)
        except Exception:
            logger.warning(
                'AOF164: le moteur a refusé le pan %s — compte historique '
                'conservé pour ce pan', zone.get('id'), exc_info=True)
            continue
        resultat = sortie['resultat']
        modules += int(resultat.modules)
        detail.append({
            'zone': zone['id'],
            'modules': int(resultat.modules),
            'hash_entree': resultat.hash_entree,
            'version_moteur': resultat.version_moteur,
            'methode': sortie['preuve']['methode'],
            'compte_optimal': sortie['preuve']['compte_optimal'],
        })
    if not detail:
        return None
    return {'modules': modules, 'pans': tuple(detail),
            'produit_panneau': getattr(produit_panneau, 'pk', None)}


def arbitrer_compte_calepinage(layout, compte_historique, *, company=None,
                               devis=None):
    """Compare ancien et nouveau compte et JOURNALISE l'écart, ou rend ``None``.

    ``None`` signifie « ne change rien » : drapeau baissé (cas par défaut,
    retour AVANT tout calcul et tout journal) ou moteur sans réponse.
    Sinon rend ``{'ancien', 'nouveau', 'ecart', 'retenu', 'pans',
    'hors_tolerance', 'motif'}``.

    ``retenu`` est le compte du MOTEUR tant que l'écart reste DANS la tolérance
    PVG2 (``TOLERANCE_ARBITRAGE_MODULES`` modules OU ``TOLERANCE_ARBITRAGE_PCT``
    %) — c'est le sens même de la bascule. Au-delà, l'écart n'est plus une
    correction mais une ANOMALIE : ``retenu`` reste le compte HISTORIQUE,
    ``hors_tolerance`` vaut ``True``, et l'écart part en ``logger.warning`` avec
    les DEUX comptes et la référence du devis. Jamais un remplacement
    silencieux, jamais une exception (décision fondateur : sécurité par défaut).

    PV42 — ``company``/``devis`` sont transmis au moteur pour qu'il calepine sur
    le panneau réellement vendu (PV12).
    """
    if not moteur_calepinage_actif():
        return None
    try:
        mesure = compte_moteur_du_layout(layout, company=company, devis=devis)
    except Exception:
        # Une panne du moteur ne fait JAMAIS échouer une création de devis :
        # on journalise et on garde le compte historique.
        logger.warning('AOF164: moteur indisponible — compte historique '
                       'conservé pour ce devis', exc_info=True)
        return None
    if mesure is None:
        return None
    ancien = int(compte_historique or 0)
    nouveau = int(mesure['modules'])
    ecart = nouveau - ancien
    logger.info(
        'AOF164: bascule moteur ACTIVE — compte TypeScript %d, compte moteur '
        '%d, écart %+d (%d pan(s) calepiné(s))',
        ancien, nouveau, ecart, len(mesure['pans']))

    # PVG2 — garde de tolérance : au-delà, on GARDE le compte historique et on
    # alerte (le journal porte les deux comptes + la référence, pour que
    # l'anomalie soit diagnosticable sans rejouer le calcul).
    if not _ecart_dans_la_tolerance(ancien, ecart):
        motif = 'écart au-delà de la tolérance — compte historique conservé'
        logger.warning(
            'PVG2: %s (devis %s) : compte TypeScript %d, compte moteur %d, '
            'écart %+d — tolérance %d module(s) ou %.1f %%',
            motif, getattr(devis, 'reference', '?') or '?', ancien, nouveau,
            ecart, TOLERANCE_ARBITRAGE_MODULES, TOLERANCE_ARBITRAGE_PCT)
        return {'ancien': ancien, 'nouveau': nouveau, 'ecart': ecart,
                'retenu': ancien, 'pans': mesure['pans'],
                'hors_tolerance': True, 'motif': motif}

    return {'ancien': ancien, 'nouveau': nouveau, 'ecart': ecart,
            'retenu': nouveau, 'pans': mesure['pans'],
            'hors_tolerance': False, 'motif': ''}


def _cible_panneaux_du_layout(layout, toiture):
    """Nombre de panneaux VOULU par un layout (même lecture que la création).

    QJR165 — ACCÈS au lecteur unique ; il n'y a PLUS de seconde chaîne de
    repli ici. La promesse « même lecture que la création » de cette docstring
    était fausse depuis QJR97 : elle redevient vraie. Nom et signature
    CONSERVÉS —
    ``resynchronisation`` et ``dimensionnement.plafond_toit_du_devis`` les
    importent tels quels.
    """
    return lire_layout(layout, toiture=toiture).compte


def _watt_du_layout(layout, toiture, cible_panneaux):
    """Wattage unitaire annoncé par le layout, ou déduit de son kWc.

    QJR165 — ACCÈS au lecteur unique (cf. ``lire_layout``). ``cible_panneaux``
    reste le compte SUR LEQUEL déduire : l'appelant a déjà arrêté le sien.
    """
    return lire_layout(layout, toiture=toiture, compte=cible_panneaux).watt


# ════════════════════════════════════════════════════════════════════════════
# AUTO-PIPELINE — DU TRACÉ DU CLIENT AU DEVIS BROUILLON, SANS MAIN HUMAINE
# ════════════════════════════════════════════════════════════════════════════
#
# ORDRE FONDATEUR (26/08/2026) : « si le client dessine son toit dans le
# tunnel, alors une fois que le lead arrive dans notre ERP ça crée
# automatiquement le devis automatique, et l'outil de calepinage dessine les
# panneaux tout seul — le commercial ne fait que VÉRIFIER ce qui a été fait
# automatiquement. »
#
# CE QUI N'EST PAS RÉINVENTÉ ICI (et ne doit jamais l'être) :
#   · le DIMENSIONNEMENT reste celui de ``build_devis_auto`` — facture d'hiver
#     ou profil horaire réel : exactement les mêmes chiffres qu'une création
#     manuelle, aucun nombre neuf n'entre dans le devis par ce chemin ;
#   · la COMPOSITION reste la source unique U3 (``composition_residentielle`` /
#     ``composition_deux_optimiseurs``) ;
#   · la NUMÉROTATION reste ``core.numbering`` (highest-used+1, JAMAIS
#     count()+1) via ``build_devis_from_layout`` ;
#   · le DESSIN des panneaux reste l'affaire du moteur de calepinage de
#     l'écran — celui-là même que le tunnel public utilise pour son estimation.
#     Un layout sérialisé ne transporte JAMAIS de pose : ``deserializeLayout``
#     rend ses zones avec ``result: null, renderPlan: null`` et l'écran re-pave
#     au boot. Poser des panneaux côté serveur avec un SECOND moteur ne ferait
#     donc qu'inventer un dessin que l'écran contredirait aussitôt.
#
# CE QUE CE BLOC FAIT, ET RIEN D'AUTRE : il transforme ``Lead.roof_outline`` en
# une VRAIE zone de toit dans le layout du devis, pour que l'écran ait le
# contour du client à paver au boot au lieu d'une page blanche.

_AUTO_ZONE_ID = 'area-1'
# ── CE QUE LA ZONE AUTOMATIQUE NE DIT PAS, ET POURQUOI (F2) ─────────────────
# Elle n'écrit NI ``roofType``, NI ``pitchDeg``, NI ``facingAzimuthDeg``.
#
# La première version les posait aux valeurs de la zone vierge du builder
# (``newAreaRecord()`` : flat / 22° / 180°) en se disant « ce sont les réglages
# que l'écran afficherait de toute façon ». À l'écran, oui — et ils y sont
# VISIBLEMENT MODIFIABLES. Mais un champ écrit dans le layout ne s'arrête pas
# à l'écran : il descend ``extract_roof_config`` → ``_pans_geometry`` →
# ``calepinage_options.parametres_site_publics``, et le CLIENT lisait alors
# « Orientation Sud (180°) · Inclinaison 22° · Toit plat » dans l'annexe
# « paramètres du site » de sa proposition — présenté comme un relevé, sur un
# toit que personne n'a mesuré. Avant ce lot ces trois champs étaient ABSENTS
# d'un devis automatique ; ils le restent.
#
# L'écran, lui, ne perd rien : ``deserializeLayout`` applique ses propres
# valeurs par défaut quand la clé manque (apps/web prefill.ts) — donc le
# commercial voit et corrige exactement ce qu'il verrait après avoir tracé le
# contour à la main. Dès qu'il enregistre, ``serializeLayout`` écrit les trois
# champs pour de bon et l'annexe les publie : un chiffre n'est publié qu'une
# fois qu'un humain l'a regardé.


def contour_client_lnglat(lead):
    """Le tracé du client en ``[[lng, lat], …]`` (convention builder), ou ``[]``.

    MÊMES règles que ``referenceContourRing`` (apps/web prefill.ts) et que
    ``normaliserContour`` (frontend traceToit.js) : les DEUX formes réellement
    stockées dans ``Lead.roof_outline`` — ``[lat, lng]`` (posée par le webhook,
    cf. ``_clean_roof_outline``) et ``{lat, lng}`` (import / saisie manuelle) —
    le MÊME bornage lat ∈ [-90, 90] / lng ∈ [-180, 180], et le MÊME seuil de
    3 sommets (un polygone commence à 3). Jamais une version plus permissive :
    un contour que l'écran refuse de dessiner ne doit pas devenir une zone
    côté serveur.
    """
    brut = getattr(lead, 'roof_outline', None)
    if not isinstance(brut, (list, tuple)):
        return []
    anneau = []
    for point in brut:
        if isinstance(point, dict):
            lat, lng = point.get('lat'), point.get('lng')
        elif isinstance(point, (list, tuple)) and len(point) >= 2:
            lat, lng = point[0], point[1]
        else:
            continue
        try:
            lat, lng = float(lat), float(lng)
        except (TypeError, ValueError):
            continue
        # Ce test rejette AUSSI les NaN : toute comparaison avec NaN est
        # fausse, donc `-90 <= nan <= 90` l'est, et le point est écarté. (Un
        # second garde-fou `lat != lat` vivait ici : il était inatteignable.)
        if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
            continue
        anneau.append([lng, lat])
    return anneau if len(anneau) >= 3 else []


def aire_contour_m2(contour):
    """L'aire (m²) d'un contour ``[[lng, lat], …]``, ou ``None``.

    ACAL281 — délègue à ``core.calepinage.geo.aire_contour_m2`` : MÊME
    projection (sphère R = 6 378 137 m) que ``calepinage_options.anneau_enu``
    et que l'écran, puis lacet de souliers. Aucune approximation maison :
    c'est la surface du polygone que le client a réellement tracé.
    """
    from core.calepinage.geo import aire_contour_m2 as _aire

    return _aire(contour)


def _aire_portee(valeur):
    """Une aire PORTÉE par le document (> 0, nombre fini), ou ``None``."""
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
        return None
    valeur = float(valeur)
    if not math.isfinite(valeur) or valeur <= 0:
        return None
    return valeur


def aire_du_pan(zone):
    """ACAL276 — l'aire (m²) d'un pan, ou ``None``.

    ``result.areaM2`` d'abord (zone synthétique d'auto-devis, pan pavé par le
    builder), puis les replis DÉJÀ lus par ``extract_roof_config`` (bloc
    ``geometry`` WJ24, ``areaM2`` à la racine de la zone) ; à défaut, l'aire
    PROJETÉE du contour dessiné (``vertices`` ``[[lng, lat], …]`` ou
    ``{lat, lng}``) par :func:`aire_contour_m2` — même projection que l'écran.
    Un pan dessiné mais jamais pavé n'a donc plus une surface de 0.
    """
    if not isinstance(zone, dict):
        return None
    for bloc in (zone.get('result'), zone.get('geometry'), zone):
        if isinstance(bloc, dict):
            aire = _aire_portee(bloc.get('areaM2'))
            if aire is not None:
                return aire
    sommets = []
    for point in zone.get('vertices') or []:
        if isinstance(point, dict):
            point = [point.get('lng'), point.get('lat')]
        if isinstance(point, (list, tuple)) and len(point) >= 2:
            sommets.append([point[0], point[1]])
    return aire_contour_m2(sommets)


def plafond_physique_du_contour(contour, produit_panneau):
    """Le nombre de panneaux qu'un toit de cette SURFACE ne peut PAS dépasser.

    ``None`` dès qu'une donnée manque (contour illisible, produit sans
    dimensions) — jamais un plafond deviné.

    C'est une BORNE PHYSIQUE DURE, pas un calepinage : ``aire du contour ÷ aire
    d'un panneau``. Deux propriétés en font le seul plafond honnête qu'on
    puisse poser côté serveur :

    * elle ne dépend d'AUCUN paramètre que le client ne nous a pas donné (ni
      pente, ni azimut, ni retrait de rive, ni obstacles) — donc elle
      n'invente rien ;
    * elle est LARGE par construction (un calepinage réel tient toujours
      nettement moins que la surface brute), donc elle ne rabote jamais un
      devis légitime : elle n'attrape que les cibles physiquement impossibles.

    Le vrai plafond de calepinage, lui, est prononcé par le SEUL moteur qui
    dessine — celui de l'écran, au boot — qui pose le maximum tenable et lève
    son avertissement existant. Poser ici un second moteur (pente et azimut
    devinés) donnerait un nombre que l'écran contredirait : c'est exactement le
    piège que le drapeau ``USE_MOTEUR_CALEPINAGE`` (réglage
    ``settings.USE_MOTEUR_CALEPINAGE``, variable d'environnement, défaut OFF —
    ACAL331) tient fermé.

    LES DIMENSIONS VIENNENT DE LA FICHE TECHNIQUE, PAS DU PRODUIT. Une première
    version lisait ``produit.longueur_mm``/``largeur_mm`` : ces champs
    n'existent PAS sur ``stock.Produit``, ils vivent sur sa ``FicheTechnique``
    (PV5). ``getattr(..., None)`` rendait donc silencieusement ``None`` et le
    plafond ne s'appliquait JAMAIS — une garde morte, verte en apparence. On
    passe désormais par ``stock.selectors.kit_from_produit`` (lecture cross-app
    sanctionnée, jamais ``stock.models``), qui est déjà LA source unique des
    dimensions réelles d'un module pour le moteur de calepinage : elle rend
    ``None`` dès qu'une des grandeurs requises manque, exactement la règle
    « on ne devine jamais une géométrie ».

    Conséquence assumée : sans fiche technique complète sur le panneau, il n'y
    a PAS de plafond. C'est le bon défaut — un plafond inventé serait pire que
    pas de plafond.
    """
    aire_toit = aire_contour_m2(contour)
    if not aire_toit or produit_panneau is None:
        return None
    try:
        from apps.stock.selectors import kit_from_produit
        kit = kit_from_produit(produit_panneau)
    except Exception:  # noqa: BLE001 — un catalogue illisible n'est pas un plafond
        logger.warning('Auto-devis: dimensions du panneau illisibles — aucun '
                       'plafond de toit appliqué.', exc_info=True)
        return None
    if kit is None:
        return None
    aire_panneau = float(kit.module_long_m) * float(kit.module_court_m)
    if aire_panneau <= 0:
        return None
    plafond = int(aire_toit // aire_panneau)
    return plafond if plafond > 0 else None


def zone_toit_depuis_contour(lead, *, panneaux, kwc=None):
    """Le fragment de layout roofPro11 qui porte le tracé du CLIENT, ou ``{}``.

    Rend exactement les clés que ``SerializedLayout`` déclare — ``version``,
    ``pin``, ``outline``, ``zones``, ``activeAreaId`` — donc ce que
    ``deserializeLayout`` / ``hydrateFromDevis`` savent déjà relire : l'écran
    ouvre alors sur la zone du client, la ferme et la pave, sans qu'un
    commercial ait à re-tracer quoi que ce soit.

    ``outline`` est en ``[[lat, lng], …]`` et ``zones[].vertices`` en
    ``[[lng, lat], …]`` : ce sont les DEUX conventions de ``serializeLayout``,
    respectées telles quelles (les inverser ferait atterrir le toit à des
    milliers de kilomètres).

    ``neededPanels`` porte la cible du devis et ``neededAuto`` vaut ``False`` :
    c'est le nombre VENDU qui pilote l'optimiseur, jamais un remplissage
    « au mieux ». Si la cible ne tient pas, l'écran pose le maximum et lève son
    avertissement — le plafond est prononcé par le moteur qui dessine.
    """
    contour = contour_client_lnglat(lead)
    if not contour:
        return {}
    # QJR598 — LE repère toit du lead (le GPS corrigé prime sur l'épingle) ;
    # un repère hors du contour fait du contour un simple calque : on
    # n'auto-calepine pas un toit que l'équipe a déplacé ailleurs.
    from apps.crm.selectors import repere_toit
    pin, _source, contour_utilisable = repere_toit(lead)
    if not contour_utilisable:
        return {}
    if pin is None:
        # Centroïde du contour — MÊME repli que ``centroidOf`` côté écran
        # (moyenne des sommets), une valeur DÉRIVÉE du tracé réel, jamais une
        # position inventée.
        pin = {'lng': sum(p[0] for p in contour) / len(contour),
               'lat': sum(p[1] for p in contour) / len(contour)}
    cible = max(int(panneaux or 0), 0)
    # ``result`` par pan — les TROIS chiffres que ``extract_roof_config`` lit
    # pour écrire ``etude_params['toiture']``. Sans lui, la config toiture d'un
    # devis automatique repartait à « 0 kWc / 0 m² » : un zéro affiché est pire
    # qu'une absence. Les trois sont DÉRIVÉS et traçables — le compte est la
    # cible réellement composée, la puissance est celle du devis (le MÊME
    # ``result.kwc`` racine), et la surface est celle du polygone que le client
    # a tracé, mesurée par ``aire_contour_m2``. Aucun n'est neuf.
    resultat_pan = {'count': cible}
    if kwc:
        resultat_pan['kwc'] = float(kwc)
    aire = aire_contour_m2(contour)
    if aire:
        resultat_pan['areaM2'] = round(aire, 2)
    return {
        'version': 2,
        'pin': pin,
        'outline': [[lat, lng] for lng, lat in contour],
        'zones': [{
            'id': _AUTO_ZONE_ID,
            'label': 'Toit du client',
            'vertices': [list(p) for p in contour],
            'obstacles': [],
            # PAS de roofType / pitchDeg / facingAzimuthDeg : voir le bloc
            # « CE QUE LA ZONE AUTOMATIQUE NE DIT PAS » ci-dessus. `facingManual`
            # reste faux et le dit : personne n'a fixé d'orientation.
            'facingManual': False,
            'neededPanels': cible,
            'neededAuto': False,
            # Additif : ``deserializeLayout`` ignore les clés qu'il ne déclare
            # pas (il repave au boot de toute façon) — ceci ne sert qu'aux
            # lecteurs SERVEUR du layout.
            'result': resultat_pan,
        }],
        'activeAreaId': _AUTO_ZONE_ID,
        'source': 'lead',
        # Marqueur INTERNE (préfixe `_`, comme ``_pans_geometry``) : il dit que
        # cette zone vient du tracé du client et n'a jamais été validée par un
        # humain. L'écran s'en sert pour afficher « à vérifier » ; personne ne
        # doit le prendre pour une géométrie relevée.
        '_origine_calepinage': 'contour_client',
    }


# ── PONTS M3 : noms hébergés ailleurs ────────────────────────────────────────
# Imports EN BAS DE FICHIER (voir la docstring) : ils s'exécutent après toutes
# les définitions de ce module, donc l'ordre de chargement ne peut jamais faire
# lire un module à moitié construit.
from apps.ventes.domain.catalogue import (  # noqa: E402,F401
    _is_hybrid_inverter,
    _is_panel,
    _is_reseau_inverter,
    _pick_batterie,
    _pick_product,
    _plage_batterie_de_l_onduleur,
)
from apps.ventes.domain.lignes import (  # noqa: E402,F401
    CIBLE_WATT_DEFAUT,
    LAYOUT_WATT_REPLI,
    _classe_ligne,
    _lignes_produit,
)
from apps.ventes.domain.composition import _v_txt  # noqa: E402,F401
from apps.ventes.domain.gammes import gamme_nom  # noqa: E402,F401
from apps.ventes.domain.etape_composer import (  # noqa: E402,F401
    COMPOSITION_AVEC,
    COMPOSITION_LES_DEUX,
    COMPOSITION_SANS,
    MSG_AUCUN_PANNEAU,
    IntentionComposition,
    verifier,
)
