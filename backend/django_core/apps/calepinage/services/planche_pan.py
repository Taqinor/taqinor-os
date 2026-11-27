"""ACAL590 — la FEUILLE A4 PAR PAN du plan de pose.

Le plan de pose A3 montre le site entier : tous les modules y sont verts et les
chaînes ne sont que des lignes de texte. L'équipe qui monte un pan à la fois
reçoit ici, après les feuilles A3 (inchangées), une page A4 paysage PAR PAN
posé : chaque module teinté de la couleur de sa chaîne (``PALETTE_CHAINES`` —
la MÊME que l'écran et le plan de câblage), son numéro, et la flèche de chaque
chaîne, du premier au dernier numéro.

RIEN n'est recalculé : la table module -> chaîne et la teinte sont LUES par
``documents/plan_cablage._plan_de_cablage`` (importé, non copié) ; le numéro
est celui de ``panels[].n`` (``production.numeros_des_modules``, via la clé
« <pan>#<n> »). Aucun « + » ni « − » : l'affectation ne connaît pas la
polarité électrique — même convention que le plan de câblage (ACAL643),
même phrase de légende (``plan_cablage.LEGENDE_SENS``). Sans chaîne publiée,
les modules restent neutres et la feuille le dit. Aucun montant.
"""
from __future__ import annotations

import math
import textwrap
from html import escape

from core.calepinage.geometrie import point_dans_polygone

from .chaines import COULEUR_NON_AFFECTE
from .planche import (
    GRIS_PAN, GRIS_TEXTE, MENTION_NON_CHAINE, NOIR, ORANGE, TRAIT_MODULE,
    TRAIT_PAN, PlancheRefusee, _barre_echelle_svg, _cote_horizontale,
    _cote_verticale, _fleche_nord_svg, _n, _polygone, _transformation,
    _verifier_absence_d_argent, pied_du_calepinage, texte_de_longueur,
)

#: La feuille A4 paysage (mm) : le dessin à gauche, la colonne de légende à
#: droite, le pied en bas.
FORMAT_A4_MM = (297.0, 210.0)
CADRE_DESSIN_MM = (10.0, 24.0, 196.0, 148.0)
COLONNE_X_MM = 214.0

#: Les règles de page ajoutées au HTML du plan de pose (A4 paysage nommée).
STYLE_FEUILLE_PAN = ('@page pan{size:A4 landscape;margin:0;}'
                     '.feuille-pan{page:pan;page-break-before:always;}')


def _libelle_de_pan(pan):
    return pan.get('libelle') or pan.get('repere') or ''


def _plan_des_chaines(roof_layout, affectation):
    """``(modules, entrees)`` — LUS sur le plan de câblage ; sans chaîne
    publiée : les modules du document, neutres, et ``entrees`` vide."""
    from .documents.plan_cablage import (
        PlanCablageRefuse, _modules_du_plan, _plan_de_cablage,
    )
    from .planche import geometrie_de_planche

    try:
        plan = _plan_de_cablage(roof_layout, affectation)
    except PlanCablageRefuse:
        geometrie = geometrie_de_planche(roof_layout)
        return ([dict(m, chaine=None, couleur=None, rang=None)
                 for m in _modules_du_plan(roof_layout, geometrie)], [])
    return plan['modules'], plan['legende']


def _numero(module):
    return str(module['module']).rpartition('#')[2]


def _ordre_dans_la_chaine(module, rang_de_pan=0):
    """ACAL1719 (revue) — l'ordre du plan de câblage
    (``plan_cablage.cle_dans_la_chaine``) : le rang du module dans sa chaîne,
    celui du DXF ; en repli, le pan puis le numéro, un repère sans numéro
    lisible après."""
    from .documents.plan_cablage import cle_dans_la_chaine

    numero = _numero(module)
    return cle_dans_la_chaine(module, (rang_de_pan, 0, int(numero))
                              if numero.isdigit() else (rang_de_pan, 1, 0))


def _chaines_du_pan(modules_du_pan, modules, entrees, pans):
    """Par chaîne présente sur ce pan, dans l'ordre d'apparition :
    ``{chaine, couleur, modules (dans l'ordre de la chaîne), total, suite,
    bouts}``."""
    from .documents.plan_cablage import bouts_publies

    totaux = {e['chaine']: e['modules'] for e in entrees}
    ordre = {pan['repere']: rang for rang, pan in enumerate(pans)}
    noms = {pan['repere']: _libelle_de_pan(pan) for pan in pans}
    chaines = {}
    for module in modules_du_pan:
        if module['chaine'] is not None:
            chaines.setdefault(module['chaine'], []).append(module)
    sortie = []
    for chaine, lot in chaines.items():
        lot = sorted(lot, key=_ordre_dans_la_chaine)
        autres = sorted({m['pan'] for m in modules
                         if m['chaine'] == chaine
                         and m['pan'] != lot[0]['pan']},
                        key=lambda cle: ordre.get(cle, 0))
        # ACAL1719 — « + » / « − » seulement sur le pan du premier / dernier
        # module de TOUTE la chaîne (même ordre que le plan de câblage).
        tous = sorted((m for m in modules if m['chaine'] == chaine),
                      key=lambda m: _ordre_dans_la_chaine(
                          m, ordre.get(m['pan'], 0)))
        publies = bouts_publies(tous, totaux.get(chaine))
        sortie.append({
            'bouts': (tous[0] is lot[0] and publies[0],
                      tous[-1] is lot[-1] and publies[1]),
            'seul': len(tous) < 2,
            'chaine': chaine, 'couleur': lot[0]['couleur'], 'modules': lot,
            'total': totaux.get(chaine), 'suite': [noms.get(c, c)
                                                   for c in autres]})
    return sortie


def _etendue_du_pan(pan, modules_du_pan, zones=()):
    points = list(pan['points'])
    for zone in zones:
        points.extend(zone['points'])
    for module in modules_du_pan:
        points.extend(module['coins'] or [module['centre']])
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return (min(xs), min(ys), max(xs), max(ys))


def _dessin_du_module(module, vers_feuille):
    """Un module teinté de sa chaîne, avec son numéro (neutre sans chaîne)."""
    couleur = module['couleur']
    centre = vers_feuille(module['centre'])
    if module['coins'] is None:
        forme = ('<circle cx="%s" cy="%s" r="1.4" fill="%s" />'
                 % (_n(centre[0]), _n(centre[1]),
                    couleur or COULEUR_NON_AFFECTE))
    else:
        forme = _polygone(module['coins'], vers_feuille,
                          contour=couleur or COULEUR_NON_AFFECTE,
                          remplissage=couleur or 'none', trait=TRAIT_MODULE)
    texte = ('<text x="%s" y="%s" font-size="3" font-weight="bold" '
             'text-anchor="middle" fill="%s">%s</text>'
             % (_n(centre[0]), _n(centre[1] + 3.2),
                '#ffffff' if couleur else GRIS_TEXTE,
                escape(_numero(module))))
    return forme + texte


def _reperes_de_chaine(chaine, vers_feuille):
    """La flèche de la chaîne sur ce pan (``plan_cablage._fleche_de_chaine``,
    la même que le plan de câblage) : par les centres, du premier au dernier
    numéro, encre foncée, « + » et « − » aux bouts (ACAL1719) ; rien pour une
    chaîne d'un seul module. ACAL1719 (revue) — le bout d'une chaîne seul sur
    ce pan garde son signe, sans flèche."""
    from .documents.plan_cablage import _fleche_de_chaine, signes_de_bout

    lot = chaine['modules']
    if len(lot) >= 2:
        return [_fleche_de_chaine(lot, vers_feuille, chaine['bouts'])]
    if chaine.get('seul') or not any(chaine['bouts']):
        return []
    point = vers_feuille(lot[0]['centre'])
    return ['<g class="bout-chaine" data-chaine="%s">%s</g>'
            % (escape(str(chaine['chaine']), quote=True),
               signes_de_bout(point, point, chaine['bouts']))]


def _colonne_de_legende(chaines, sans_chaine):
    """Les lignes de la colonne de droite : ``[(couleur | None, texte)]``."""
    lignes = []
    if sans_chaine:
        lignes.append((None, MENTION_NON_CHAINE))
    for chaine in chaines:
        nombre = len(chaine['modules'])
        lignes.append((chaine['couleur'], 'Chaîne %s — %d module%s sur ce pan'
                       % (chaine['chaine'], nombre,
                          '' if nombre < 2 else 's')))
        if chaine['suite']:
            lignes.append((None, '   suite sur %s'
                           % ', '.join(chaine['suite'])))
    return lignes


def _legende_a4(lignes, x, y):
    morceaux = ['<text x="%s" y="%s" font-size="3.6" font-weight="bold" '
                'fill="%s">LÉGENDE</text>' % (_n(x), _n(y), NOIR)]
    y += 6.0
    for couleur, texte in lignes:
        if couleur:
            morceaux.append('<rect x="%s" y="%s" width="4" height="3" '
                            'fill="%s" />' % (_n(x), _n(y - 2.4), couleur))
        for ligne in textwrap.wrap(texte, 46, subsequent_indent='  ') or ['']:
            morceaux.append('<text x="%s" y="%s" font-size="3.2" fill="%s">'
                            '%s</text>' % (_n(x + (6.0 if couleur else 0.0)),
                                           _n(y), NOIR, escape(ligne)))
            y += 4.4
        y += 0.6
    return morceaux, y


# ── ACAL591 — les distances aux rives et les zones interdites ──────────────

MENTION_PROJECTION = ('Distances mesurées en plan, projection horizontale '
                      'du pan')
MOTIF_SANS_ORIENTATION = ('orientation du module non enregistrée : '
                          'distances non calculées')
#: Les quatre sens de mesure (repère local : le nord est +y, l'est +x).
SENS_DE_MESURE = (('N', (0.0, 1.0)), ('S', (0.0, -1.0)),
                  ('E', (1.0, 0.0)), ('O', (-1.0, 0.0)))
_TOLERANCE = 1e-9
#: ACAL1712 — un sommet à moins d'1 mm d'une rive est POSÉ sur elle (le pavage
#: colle les modules au contour, à l'arrondi près) : un écart de mesure, pas une cote.
_CONTACT_M = 1e-3


def _portee_jusqu_au_contour(point, sens, contour):
    """La distance de ``point`` au contour, mesurée PARALLÈLEMENT à ``sens``
    (le premier croisement), ou ``None`` : rien n'est supposé.

    ACAL1712 — un sommet posé SUR une rive (à ``_CONTACT_M`` près) : si
    ``sens`` sort du pan par cette rive (normale extérieure dans le sens de la
    mesure), la cote vaut 0 (le champ touche CETTE rive) ; s'il y entre, la rive
    de départ n'est pas la rive en face et ne compte pas (elle faisait lire
    E = 0 à un champ collé à l'ouest)."""
    contour = list(contour)
    # Orientation du contour : la normale extérieure d'une arête (ex, ey) est
    # (ey, −ex) pour un contour direct, (−ey, ex) sinon.
    signe = 1.0 if sum(contour[i - 1][0] * p[1] - p[0] * contour[i - 1][1]
                       for i, p in enumerate(contour)) >= 0 else -1.0
    croisements = []
    for rang, a in enumerate(contour):
        b = contour[(rang + 1) % len(contour)]
        ex, ey = b[0] - a[0], b[1] - a[1]
        denominateur = sens[0] * ey - sens[1] * ex
        if abs(denominateur) < _TOLERANCE:
            continue
        dx, dy = a[0] - point[0], a[1] - point[1]
        t = (dx * ey - dy * ex) / denominateur
        u = (dx * sens[1] - dy * sens[0]) / denominateur
        if t >= -_CONTACT_M and -_TOLERANCE <= u <= 1.0 + _TOLERANCE:
            sortie = signe * (ey * sens[0] - ex * sens[1]) > 0
            croisements.append((t, sortie))
    if any(t <= _CONTACT_M and sortie for t, sortie in croisements):
        return 0.0  # un zéro POSITIF : jamais « −0,00 »
    loin = [t for t, _sortie in croisements if t > _CONTACT_M]
    return min(loin) if loin else None


def _distances_aux_rives(pan, modules_du_pan):
    """``({'N'|'S'|'E'|'O': {distance, depart, arrivee}}, motif)``.

    Pour chaque côté : la PLUS PETITE distance, parallèle à l'axe, entre un
    sommet du rectangle rendu d'un module (``coins_du_module``, jamais un
    rectangle supposé) et le contour du pan. Un module sans emprise (pose ou
    azimut non enregistrés) : aucune distance, et le motif le dit."""
    if not modules_du_pan:
        return {}, ''
    if any(m['coins'] is None for m in modules_du_pan):
        return {}, MOTIF_SANS_ORIENTATION
    sommets = [coin for m in modules_du_pan for coin in m['coins']]
    sortie = {}
    for cote, sens in SENS_DE_MESURE:
        meilleur = None
        for sommet in sommets:
            portee = _portee_jusqu_au_contour(sommet, sens, pan['points'])
            if portee is not None and (meilleur is None
                                       or portee < meilleur[0]):
                meilleur = (portee, sommet)
        if meilleur is not None:
            portee, sommet = meilleur
            sortie[cote] = {
                'distance': portee, 'depart': sommet,
                'arrivee': (sommet[0] + sens[0] * portee,
                            sommet[1] + sens[1] * portee)}
    return sortie, ''


def _segments_se_croisent(a, b, c, d):
    def cote(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    return (cote(a, b, c) * cote(a, b, d) < 0
            and cote(c, d, a) * cote(c, d, b) < 0)


def _polygones_se_recoupent(p, q):
    """Vrai si deux polygones se recouvrent (sommet dans l'autre, ou arêtes
    qui se croisent) — l'appartenance est ``point_dans_polygone``."""
    p, q = list(p), list(q)
    if any(point_dans_polygone(x, q) for x in p) \
            or any(point_dans_polygone(x, p) for x in q):
        return True
    return any(_segments_se_croisent(p[i], p[(i + 1) % len(p)],
                                     q[j], q[(j + 1) % len(q)])
               for i in range(len(p)) for j in range(len(q)))


def _distance_point_segment(point, a, b):
    ex, ey = b[0] - a[0], b[1] - a[1]
    carre = ex * ex + ey * ey
    t = 0.0 if carre == 0 else max(0.0, min(1.0, (
        (point[0] - a[0]) * ex + (point[1] - a[1]) * ey) / carre))
    return math.hypot(point[0] - (a[0] + t * ex), point[1] - (a[1] + t * ey))


def _distance_entre_polygones(p, q):
    p, q = list(p), list(q)
    return min([_distance_point_segment(x, q[i], q[(i + 1) % len(q)])
                for x in p for i in range(len(q))]
               + [_distance_point_segment(x, p[i], p[(i + 1) % len(p)])
                  for x in q for i in range(len(p))])


def _cotes_des_zones(pan, modules_du_pan, zones):
    """Une entrée par zone interdite qui recoupe le pan : ``{repere,
    libelle, largeur_m, hauteur_m, distance_m, recouvre, points}``. La
    distance (bord de la zone au module le plus proche) et « recouvre »
    exigent l'emprise de chaque module ; sans elle : ``None`` / ``False``."""
    sortie = []
    emprises = [m['coins'] for m in modules_du_pan]
    mesurable = bool(emprises) and all(c is not None for c in emprises)
    for zone in zones or ():
        points = zone['points']
        if not _polygones_se_recoupent(pan['points'], points):
            continue
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        recouvre = mesurable and any(_polygones_se_recoupent(points, c)
                                     for c in emprises)
        proche = mesurable and not recouvre
        sortie.append({
            'repere': zone['repere'], 'libelle': zone.get('libelle') or '',
            'largeur_m': max(xs) - min(xs), 'hauteur_m': max(ys) - min(ys),
            'recouvre': recouvre, 'points': points,
            'distance_m': (min(_distance_entre_polygones(points, c)
                               for c in emprises) if proche else None)})
    return sortie


#: ACAL1712 — décalage (mm de feuille) de la lettre d'une cote depuis le bout de
#: sa cote, vers l'extérieur du champ (la feuille : y croît vers le bas).
_DECALAGE_LETTRE = {'N': (-4.0, -1.5), 'S': (-4.0, 4.0), 'E': (1.5, 7.0), 'O': (-4.5, 7.0)}


def _cotes_dessinees(distances, zones, vers_feuille):
    """Les cotes de rive (lettre + valeur) et les cotes d'emprise des zones."""
    morceaux = []
    for cote, mesure in distances.items():
        (x0, y0), (x1, y1) = mesure['depart'], mesure['arrivee']
        trace = (_cote_horizontale(x0, x1, y0, vers_feuille) if cote in 'EO'
                 else _cote_verticale(y0, y1, x0, vers_feuille))
        # ACAL1712 — la lettre se pose au bout de SA cote (côté rive), décalée
        # vers l'extérieur, et reste dans la feuille : quatre cotes nulles au même
        # sommet ne s'empilent plus au coin haut-gauche (x = −2 mesuré).
        bout = vers_feuille((x1, y1))
        dx, dy = _DECALAGE_LETTRE[cote]
        lx, ly = bout[0] + dx, bout[1] + dy
        # ACAL1935 — la lettre se pose HORS de la boîte du texte de la cote (largeur ≈ 0,6 × corps par
        # caractère) : une cote courte n'a plus sa valeur sous la lettre E / O, ni sa lettre N / S sur la valeur.
        a, b = vers_feuille((x0, y0)), vers_feuille((x1, y1))
        demi = 0.6 * 3.2 * len(texte_de_longueur(abs((x1 - x0) if cote in 'EO' else (y1 - y0)))) / 2.0
        if cote in 'EO':
            milieu = (a[0] + b[0]) / 2.0
            # Les deux lettres E et O se posent À DROITE de leur valeur : le bord gauche de la feuille est
            # déjà pris par les cotes verticales tournées.
            lx = max(lx, milieu + demi + 1.0) if dx >= 0 else milieu + demi + 1.0
        else:
            milieu = (a[1] + b[1]) / 2.0
            ly = min(ly, milieu - demi - 1.0) if dy < 0 else max(ly, milieu + demi + 1.0 + 3.2)
        lx = min(max(lx, 1.0), FORMAT_A4_MM[0] - 4.0)
        ly = min(max(ly, 4.0), FORMAT_A4_MM[1] - 1.0)
        morceaux.append('<g data-cote="%s">%s<text x="%s" y="%s" '
                        'font-size="3.2" font-weight="bold" fill="%s">%s'
                        '</text></g>' % (cote, trace, _n(lx), _n(ly), NOIR, cote))
    for zone in zones:
        xs = [p[0] for p in zone['points']]
        ys = [p[1] for p in zone['points']]
        morceaux.append(_polygone(zone['points'], vers_feuille,
                                  contour=ORANGE, tirets='1.5 1'))
        morceaux.append(_cote_horizontale(min(xs), max(xs), min(ys),
                                          vers_feuille, couleur=ORANGE))
        morceaux.append(_cote_verticale(min(ys), max(ys), min(xs),
                                        vers_feuille, couleur=ORANGE))
    return morceaux


def _lignes_de_mesures(distances, motif, zones):
    lignes = [(None, MENTION_PROJECTION)]
    if motif:
        lignes.append((None, motif))
    lignes += [(None, '%s : %s' % (cote, texte_de_longueur(m['distance'])))
               for cote, m in distances.items()]
    for zone in zones:
        nom = zone['libelle'] or zone['repere']
        texte = 'Zone interdite %s : %s × %s' % (
            nom, texte_de_longueur(zone['largeur_m']),
            texte_de_longueur(zone['hauteur_m']))
        if zone['recouvre']:
            texte += ' — recouvre un module'
        elif zone['distance_m'] is not None:
            texte += ' — à %s du module le plus proche' % texte_de_longueur(
                zone['distance_m'])
        lignes.append((None, texte))
    return lignes


NOTE_ARRONDI_PAR_PAN = ("Arrondi par pan : la somme peut dépasser la "
                        "commande du projet")


def _encart_fixation(lignes_du_pan):
    """ACAL592 — l'encart « Fixation de ce pan » : ``[(None, texte)]``, ou
    ``[]`` (sans nomenclature, la feuille ne dit rien de plus). Une quantité
    ``None`` imprime son ``manquant``, jamais un 0."""
    from .fixation import UNITE_A_L_UNITE, _fr

    if not lignes_du_pan:
        return []
    sortie = [(None, 'Fixation de ce pan')]
    for ligne in lignes_du_pan:
        if ligne['quantite'] is None:
            sortie.append((None, '%s : %s' % (ligne['composant'],
                                              ligne['manquant'])))
        else:
            sortie.append((None, '%s : %s %s' % (
                ligne['composant'], _fr(ligne['quantite']), ligne['unite'])))
    if any(str(ligne['unite']).strip().lower() == UNITE_A_L_UNITE
           for ligne in lignes_du_pan):
        sortie.append((None, NOTE_ARRONDI_PAR_PAN))
    return sortie


# ── ACAL1065 — les repères de chantier saisis, sur la feuille de leur pan ──

MENTION_REPERES = ("Repères saisis par l'équipe d'étude — rayon saisi, "
                   "non calculé")
#: Par type de repère : (nom en clair, forme du symbole).
SYMBOLES_DE_REPERE = {
    'ancre_antichute': ('ancre antichute', 'triangle'),
    'acces': ('accès', 'carré'),
    'passage_cable': ('passage de câble', 'losange'),
    'autre': ('autre repère', 'rond'),
}


def _reperes_locaux(roof_layout):
    """Les repères de chantier du document, en mètres dans le repère de la
    planche ; ``rayon_m`` vaut ``None`` quand il n'est pas saisi."""
    from .planche import _projection

    projection = _projection(roof_layout)
    brut = (roof_layout or {}).get('reperesChantier')
    sortie = []
    for repere in brut if projection and isinstance(brut, list) else ():
        point = repere.get('point') if isinstance(repere, dict) else None
        if not (isinstance(point, (list, tuple)) and len(point) == 2):
            continue
        rayon = repere.get('rayonM')
        sortie.append({
            'type': repere.get('type') if repere.get('type')
            in SYMBOLES_DE_REPERE else 'autre',
            'texte': str(repere.get('texte') or '').strip(),
            'rayon_m': float(rayon) if isinstance(rayon, (int, float))
            and not isinstance(rayon, bool) and rayon > 0 else None,
            'point': projection.vers_local(point[1], point[0])})
    return sortie


def _etendue_avec_reperes(etendue, reperes):
    """L'étendue de la feuille, élargie pour que chaque cercle saisi tienne."""
    x0, y0, x1, y1 = etendue
    for repere in reperes:
        x, y = repere['point']
        marge = repere['rayon_m'] or 0.0
        x0, y0 = min(x0, x - marge), min(y0, y - marge)
        x1, y1 = max(x1, x + marge), max(y1, y + marge)
    return (x0, y0, x1, y1)


def _symbole_de_repere(forme, x, y):
    demi = 1.6
    if forme == 'triangle':
        coins = ((x, y - demi), (x + demi, y + demi), (x - demi, y + demi))
    elif forme == 'carré':
        coins = ((x - demi, y - demi), (x + demi, y - demi),
                 (x + demi, y + demi), (x - demi, y + demi))
    elif forme == 'losange':
        coins = ((x, y - demi), (x + demi, y), (x, y + demi), (x - demi, y))
    else:
        return ('<circle cx="%s" cy="%s" r="%s" fill="%s" stroke="%s" '
                'stroke-width="0.3" />' % (_n(x), _n(y), _n(demi), ORANGE,
                                           NOIR))
    return ('<polygon points="%s" fill="%s" stroke="%s" stroke-width="0.3" />'
            % (' '.join('%s,%s' % (_n(a), _n(b)) for a, b in coins),
               ORANGE, NOIR))


def _reperes_de_chantier(reperes, vers_feuille, echelle):
    """Le symbole, le texte et le cercle de chaque repère de cette feuille.

    Le rayon se dessine avec ``echelle`` : la MÊME transformation que les
    modules. Sans rayon saisi, aucun cercle (jamais un rayon par défaut)."""
    morceaux = []
    for repere in reperes:
        x, y = vers_feuille(repere['point'])
        if repere['rayon_m']:
            morceaux.append(
                '<circle cx="%s" cy="%s" r="%s" fill="none" stroke="%s" '
                'stroke-width="0.3" stroke-dasharray="1.5 1" />'
                % (_n(x), _n(y), _n(repere['rayon_m'] * echelle), ORANGE))
        morceaux.append(_symbole_de_repere(
            SYMBOLES_DE_REPERE[repere['type']][1], x, y))
        for rang, ligne in enumerate(textwrap.wrap(repere['texte'], 40)):
            morceaux.append(
                '<text x="%s" y="%s" font-size="3" fill="%s">%s</text>'
                % (_n(x + 3.0), _n(y + 1.0 + 3.4 * rang), NOIR, escape(ligne)))
    return morceaux


def _legende_des_reperes(reperes, hors_pan):
    """``[(None, texte)]`` : la mention, un symbole par type présent, et les
    repères hors de tout pan (sur la dernière feuille seulement)."""
    if not (reperes or hors_pan):
        return []
    lignes = [(None, MENTION_REPERES)]
    for type_ in SYMBOLES_DE_REPERE:
        if any(r['type'] == type_ for r in list(reperes) + list(hors_pan)):
            nom, forme = SYMBOLES_DE_REPERE[type_]
            lignes.append((None, '%s : %s' % (forme.capitalize(), nom)))
    for repere in hors_pan:
        lignes.append((None, 'Repère hors pan : %s' % (
            repere['texte'] or SYMBOLES_DE_REPERE[repere['type']][0])))
    return lignes


def _repartition_des_reperes(reperes, pans):
    """``({pan: [repères]}, hors_pan)`` — un repère va sur le pan (garni) qui
    le contient ; sinon il est « hors pan »."""
    par_pan, hors_pan = {}, []
    for repere in reperes:
        for pan in pans:
            if pan['modules'] and point_dans_polygone(repere['point'],
                                                      pan['points']):
                par_pan.setdefault(pan['repere'], []).append(repere)
                break
        else:
            hors_pan.append(repere)
    return par_pan, hors_pan


def _pied_a4(texte):
    lignes = str(texte or '').split('\n')
    return [('<text x="%s" y="%s" font-size="3" fill="%s">%s</text>'
             % (_n(10.0), _n(FORMAT_A4_MM[1] - 4.0 - 3.6 * rang),
                GRIS_TEXTE, escape(ligne)))
            for rang, ligne in enumerate(lignes) if texte]


def _feuille_de_pan(pan, modules, entrees, pans, pied, zones=(),
                    fixation=None, reperes=(), hors_pan=()):
    """Le SVG A4 d'UN pan posé."""
    from .documents.plan_cablage import LEGENDE_SENS

    modules_du_pan = [m for m in modules if m['pan'] == pan['repere']]
    chaines = _chaines_du_pan(modules_du_pan, modules, entrees, pans)
    cotes_de_zones = _cotes_des_zones(pan, modules_du_pan, zones)
    distances, motif = _distances_aux_rives(pan, modules_du_pan)
    vers_feuille, echelle = _transformation(
        _etendue_avec_reperes(
            _etendue_du_pan(pan, modules_du_pan, cotes_de_zones), reperes),
        CADRE_DESSIN_MM)
    nom = _libelle_de_pan(pan)
    titre = '%s — plan de pose' % (
        nom if nom.lower().startswith('pan') else 'Pan %s' % nom)
    corps = [
        '<title>%s</title>' % escape(titre),
        '<rect x="0" y="0" width="%s" height="%s" fill="#ffffff" />'
        % (_n(FORMAT_A4_MM[0]), _n(FORMAT_A4_MM[1])),
        '<text x="10" y="14" font-size="6" font-weight="bold" fill="%s">%s'
        '</text>' % (NOIR, escape(titre)),
        _polygone(pan['points'], vers_feuille, contour=NOIR,
                  remplissage=GRIS_PAN, trait=TRAIT_PAN),
    ]
    corps += [_dessin_du_module(m, vers_feuille) for m in modules_du_pan]
    corps += _cotes_dessinees(distances, cotes_de_zones, vers_feuille)
    for chaine in chaines:
        corps += _reperes_de_chaine(chaine, vers_feuille)
    corps += _reperes_de_chantier(reperes, vers_feuille, echelle)
    lignes = _colonne_de_legende(chaines, not entrees)
    if any(len(chaine['modules']) > 1
           or (not chaine.get('seul') and any(chaine['bouts']))
           for chaine in chaines):
        lignes.append((None, LEGENDE_SENS))
    lignes += _lignes_de_mesures(distances, motif, cotes_de_zones)
    lignes += _encart_fixation(fixation)
    lignes += _legende_des_reperes(reperes, hors_pan)
    _verifier_absence_d_argent('\n'.join(t for _c, t in lignes))
    legende, _y = _legende_a4(lignes, COLONNE_X_MM, 28.0)
    corps += legende
    corps.append(_fleche_nord_svg(FORMAT_A4_MM[0] - 16.0, 150.0))
    corps.append(_barre_echelle_svg(COLONNE_X_MM, 182.0, echelle))
    corps += _pied_a4(pied)
    largeur, hauteur = FORMAT_A4_MM
    return ('<svg xmlns="http://www.w3.org/2000/svg" version="1.1" '
            'width="%smm" height="%smm" viewBox="0 0 %s %s">%s</svg>'
            % (_n(largeur), _n(hauteur), _n(largeur), _n(hauteur),
               '\n'.join(corps)))


def _svgs_de_pans(roof_layout, affectation, *, pied='', fixation=None):
    """Les SVG A4, un par pan qui porte un module (liste vide sinon)."""
    from .planche import geometrie_de_planche

    try:
        geometrie = geometrie_de_planche(roof_layout)
    except PlancheRefusee:
        return []
    pans = geometrie.get('pans') or []
    if not any(pan['modules'] for pan in pans):
        return []
    modules, entrees = _plan_des_chaines(roof_layout, affectation)
    garnis = [pan for pan in pans if pan['modules']]
    par_pan, hors_pan = _repartition_des_reperes(
        _reperes_locaux(roof_layout), pans)
    return [_feuille_de_pan(pan, modules, entrees, pans, pied,
                            geometrie.get('zones_interdites') or (),
                            (fixation or {}).get(pan['repere']),
                            par_pan.get(pan['repere'], ()),
                            hors_pan if pan is garnis[-1] else ())
            for pan in garnis]


def feuilles_de_pans(calepinage, *, moment=None):
    """``(style, pages)`` à passer à ``html_de_planche`` : les règles de page
    A4 et les feuilles de pan, ``('', '')`` quand aucun pan ne porte de
    module. L'affectation est celle du résultat SERVI, jamais recalculée."""
    from .. import selectors

    servi = selectors.resultat_servi(calepinage)
    electrique = (servi or {}).get('electrique') \
        if isinstance(servi, dict) else None
    affectation = list((electrique or {}).get('affectation') or [])
    from .fixation import fixation_par_pan

    pied = pied_du_calepinage(calepinage, moment=moment)
    svgs = _svgs_de_pans(getattr(calepinage, 'roof_layout', None),
                         affectation, pied=pied,
                         fixation=fixation_par_pan(calepinage))
    if not svgs:
        return '', ''
    return STYLE_FEUILLE_PAN, ''.join(
        '<div class="feuille-pan">%s</div>' % svg for svg in svgs)
