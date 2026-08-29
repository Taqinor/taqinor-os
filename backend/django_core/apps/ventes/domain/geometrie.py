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

    MÊME formule que le builder lui-même (``roofPro11/prodWindow.ts`` :
    ``aspect: res.facingAzimuthDeg - 180``), normalisée dans [-180, 180] pour
    que ±180 reste bien le Nord. Valeur illisible → ``None`` (le libellé est
    alors omis, jamais deviné)."""
    try:
        a = float(azimut)
    except (TypeError, ValueError):
        return None
    return (a - 180.0 + 180.0) % 360.0 - 180.0


def _aspect_vers_azimut_boussole(aspect):
    """Azimut PVGIS (0 = Sud) → azimut BOUSSOLE (180 = Sud), dans [0, 360).

    Réciproque de :func:`_azimut_boussole_vers_aspect`. Elle existe pour que
    ``_pans_geometry['azimut_deg']`` n'ait qu'UN SEUL repère quelle que soit la
    clé source du layout (F3) — voir :func:`extract_roof_config`. Valeur
    illisible → ``None``.
    """
    try:
        a = float(aspect)
    except (TypeError, ValueError):
        return None
    return (a + 180.0) % 360.0


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
        # ``geometry`` ensuite, ``neededPanels`` en tout dernier recours (le
        # compte SOUHAITÉ, pas le compte POSÉ).
        geo = a.get('geometry')
        if not isinstance(geo, dict):
            geo = {}
        count = int(res.get('count') or geo.get('count')
                    or a.get('neededPanels') or 0)
        kwc = float(res.get('kwc') or geo.get('kwc') or 0.0)
        surface = float(res.get('areaM2') or geo.get('areaM2')
                        or a.get('areaM2') or 0.0)
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
        brut = a.get('facingAzimuthDeg')
        if brut is not None:
            azimut_boussole = brut
            aspect_pvgis = _azimut_boussole_vers_aspect(brut)
        else:
            aspect_pvgis = a.get('aspect')
            azimut_boussole = _aspect_vers_azimut_boussole(aspect_pvgis)
        pitch = a.get('pitchDeg')
        if pitch is None:
            pitch = a.get('pitch')
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


def layout_hash(layout):
    """QJ17 — deterministic SHA-256 fingerprint of a roof layout dict.

    Used to detect duplicate ``from-layout`` submissions (same geometry re-sent
    after a network retry or a double-click).  Only the geometry-bearing keys are
    hashed (``zones``/``areas``/``pans``, ``result``, ``scenario``, ``panelWatt``,
    ``watt``, ``battery``) so that transient UI state (``pin``, ``outline``,
    ``billKwh``, ``activeAreaId``, ``renderPlan``…) never prevents deduplication.
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
    blob = _json.dumps(canonical, sort_keys=True, separators=(',', ':'),
                       default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


def validate_composition_for_layout(layout, company):
    """QJ17 — pre-flight composition check before building a devis.

    Returns ``None`` when the composition is valid.  Returns a list of French
    error strings when problems are detected (caller should surface them inline
    rather than raising a PDF error at render time).

    Rules (aligned with quote_engine/builder.py keyword classification):
    - At least 1 panel is required.
    - A battery scenario requires both a hybrid inverter AND a battery in the
      catalogue (priced); if either is missing, warn the agent.
    - A réseau scenario requires a réseau/injection inverter (priced).
    - A price-less required product blocks the composition (never auto-quote it).
    """
    if not isinstance(layout, dict):
        return ['Layout invalide — impossible de valider la composition.']

    result = dict((layout.get('result') or {}))
    nb_panneaux = int(result.get('panels') or 0)
    toiture = extract_roof_config(layout)
    if nb_panneaux <= 0 and toiture.get('nb_panneaux'):
        nb_panneaux = int(toiture['nb_panneaux'])

    errors = []
    if nb_panneaux <= 0:
        errors.append(
            'Aucun panneau détecté dans le layout. '
            'Terminez le tracé du toit et relancez l\'optimiseur avant de générer.')

    scenario = (layout.get('scenario') or '').lower()
    wants_battery = ('batterie' in scenario or 'hybride' in scenario
                     or bool(layout.get('battery')))

    if wants_battery:
        # PVMRQ — pas de devis ici (pré-vol AVANT création) ⇒ pas de gamme
        # connue : ``marque_preferee`` retombe explicitement sur le slot
        # Essentielle.
        inv = _pick_product(company, _is_hybrid_inverter, role='onduleur_hybride')
        # PVOND — garde batterie PILOTÉ PAR LA DONNÉE : la batterie retenue doit
        # entrer dans la plage batterie de l'onduleur hybride effectivement
        # choisi ci-dessus. Sans plage déclarée (ou sans fiche batterie), repli
        # sur le mot-clé « haute tension » d'hier (PVG4) — jamais de régression
        # silencieuse.
        bat = _pick_batterie(company, onduleur=inv)
        if inv is None:
            errors.append(
                'Aucun onduleur hybride disponible (ou sans prix) dans le catalogue. '
                'Ajoutez un onduleur hybride tarifé avant de générer ce devis.')
        if bat is None:
            # PVOND — DIRE POURQUOI : « aucune batterie » et « aucune batterie
            # COMPATIBLE avec cet onduleur » n'appellent pas le même geste.
            plage = _plage_batterie_de_l_onduleur(inv)
            if plage and plage[1] > 0:
                errors.append(
                    'Aucune batterie compatible tarifée pour cet onduleur '
                    '(plage %s-%s V). Ajoutez une batterie compatible tarifée, '
                    'ou choisissez un autre onduleur, avant de générer ce '
                    'devis.' % (_v_txt(plage[0]), _v_txt(plage[1])))
            else:
                errors.append(
                    'Aucune batterie disponible (ou sans prix) dans le '
                    'catalogue. Ajoutez une batterie tarifée avant de générer '
                    'ce devis.')
    else:
        inv = _pick_product(company, _is_reseau_inverter, role='onduleur_reseau')
        if inv is None:
            errors.append(
                'Aucun onduleur réseau disponible (ou sans prix) dans le catalogue. '
                'Ajoutez un onduleur réseau/injection tarifé avant de générer.')

    return errors if errors else None


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
        layout = layout or {}
        watt = layout.get('panelWatt') or layout.get('watt')
        if not watt:
            result = dict(layout.get('result') or {})
            panneaux = int(result.get('panels') or 0)
            kwc = float(result.get('kwc') or 0.0)
            if panneaux and kwc:
                watt = int(round(kwc * 1000 / panneaux / 10) * 10)
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

    Somme les pans : chacun passe par ``apps.ao.selectors.calepinage_villa``
    (lecture cross-app sanctionnée — jamais ``apps.ao.models``), qui délègue au
    moteur partagé d'AOF163. Aucune ligne AO n'est créée.

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

    from apps.ao.selectors import calepinage_villa

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
    """Nombre de panneaux VOULU par un layout (même lecture que la création)."""
    result = dict((layout or {}).get('result') or {})
    cible = int(result.get('panels') or result.get('count') or 0)
    if cible <= 0 and toiture.get('nb_panneaux'):
        cible = int(toiture['nb_panneaux'])
    return cible


def _watt_du_layout(layout, toiture, cible_panneaux):
    """Wattage unitaire annoncé par le layout, ou déduit de son kWc."""
    watt = (layout or {}).get('panelWatt') or (layout or {}).get('watt')
    if watt:
        try:
            return int(round(float(watt)))
        except (TypeError, ValueError):
            pass
    result = dict((layout or {}).get('result') or {})
    kwc = float(result.get('kwc') or toiture.get('kwc') or 0.0)
    if kwc and cible_panneaux:
        return int(round(kwc * 1000 / cible_panneaux / 10) * 10)
    return CIBLE_WATT_DEFAUT


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

    Reprojection ENU par ``calepinage_options.anneau_enu`` (la formule DÉJÀ
    partagée avec l'écran), puis lacet de souliers. Aucune approximation
    maison : c'est la surface du polygone que le client a réellement tracé.
    """
    if len(contour or []) < 3:
        return None
    from ..calepinage_options import anneau_enu

    origine = contour[0]
    anneau = anneau_enu(contour, origine)
    if len(anneau) < 3:
        return None
    aire2 = 0.0
    for i in range(len(anneau)):
        ax, ay = anneau[i]
        bx, by = anneau[(i + 1) % len(anneau)]
        aire2 += ax * by - bx * ay
    aire = abs(aire2) / 2.0
    return aire if aire > 0 else None


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
    piège que le drapeau ``USE_MOTEUR_CALEPINAGE`` existe pour tenir fermé.

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
    point = getattr(lead, 'roof_point', None)
    pin = None
    if isinstance(point, dict):
        try:
            pin = {'lat': float(point['lat']), 'lng': float(point['lng'])}
        except (KeyError, TypeError, ValueError):
            pin = None
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
    _classe_ligne,
    _lignes_produit,
)
from apps.ventes.domain.composition import _v_txt  # noqa: E402,F401
from apps.ventes.domain.gammes import gamme_nom  # noqa: E402,F401
