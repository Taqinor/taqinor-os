"""ACAL590 — la FEUILLE A4 PAR PAN du plan de pose.

Le plan de pose A3 montre le site entier : tous les modules y sont verts et les
chaînes ne sont que des lignes de texte. L'équipe qui monte un pan à la fois
reçoit ici, après les feuilles A3 (inchangées), une page A4 paysage PAR PAN
posé : chaque module teinté de la couleur de sa chaîne (``PALETTE_CHAINES`` —
la MÊME que l'écran et le plan de câblage), son numéro, et les repères « + »
(début) / « − » (fin) de chaque chaîne.

RIEN n'est recalculé : la table module -> chaîne et la teinte sont LUES par
``documents/plan_cablage._plan_de_cablage`` (importé, non copié) ; le numéro
est celui de ``panels[].n`` (``production.numeros_des_modules``, via la clé
« <pan>#<n> »). « + » et « − » suivent l'ordre de l'affectation PUBLIÉE :
ce n'est pas un relevé de câblage, et la légende le dit. Sans chaîne publiée,
les modules restent neutres et la feuille le dit. Aucun montant.
"""
from __future__ import annotations

from html import escape

from .chaines import COULEUR_NON_AFFECTE
from .planche import (
    GRIS_PAN, GRIS_TEXTE, MENTION_NON_CHAINE, NOIR, TRAIT_MODULE, TRAIT_PAN,
    PlancheRefusee, _barre_echelle_svg, _fleche_nord_svg, _n, _polygone,
    _transformation, _verifier_absence_d_argent, coins_du_module,
    pied_du_calepinage,
)

#: La feuille A4 paysage (mm) : le dessin à gauche, la colonne de légende à
#: droite, le pied en bas.
FORMAT_A4_MM = (297.0, 210.0)
CADRE_DESSIN_MM = (10.0, 24.0, 196.0, 148.0)
COLONNE_X_MM = 214.0

SIGNE_DEBUT = '+'
SIGNE_FIN = '−'
LEGENDE_REPERES = ("+ : début, − : fin, dans l'ordre de l'affectation "
                   "publiée — pas un relevé de câblage")

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


def _chaines_du_pan(modules_du_pan, modules, entrees, pans):
    """Par chaîne présente sur ce pan, dans l'ordre d'apparition :
    ``{chaine, couleur, modules (par rang), total, debut, fin, suite}``."""
    totaux = {e['chaine']: e['modules'] for e in entrees}
    ordre = {pan['repere']: rang for rang, pan in enumerate(pans)}
    noms = {pan['repere']: _libelle_de_pan(pan) for pan in pans}
    chaines = {}
    for module in modules_du_pan:
        if module['chaine'] is not None:
            chaines.setdefault(module['chaine'], []).append(module)
    sortie = []
    for chaine, lot in chaines.items():
        lot = sorted(lot, key=lambda m: m['rang'])
        autres = sorted({m['pan'] for m in modules
                         if m['chaine'] == chaine
                         and m['pan'] != lot[0]['pan']},
                        key=lambda cle: ordre.get(cle, 0))
        sortie.append({
            'chaine': chaine, 'couleur': lot[0]['couleur'], 'modules': lot,
            'total': totaux.get(chaine), 'suite': [noms.get(c, c)
                                                   for c in autres],
            'debut': lot[0]['rang'] == 1,
            'fin': lot[-1]['rang'] == totaux.get(chaine)})
    return sortie


def _etendue_du_pan(pan, modules_du_pan):
    points = list(pan['points'])
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
    """La polyligne fléchée par les centres (ordre de l'affectation publiée),
    « + » sur le premier module si la chaîne COMMENCE sur ce pan, « − » sur
    le dernier si elle y FINIT."""
    from .documents.plan_cablage import _fleche_de_chaine

    lot, couleur = chaine['modules'], chaine['couleur']
    morceaux = []
    if len(lot) > 1:
        morceaux.append(_fleche_de_chaine(lot, couleur, vers_feuille))
    for signe, module, present, decalage in (
            (SIGNE_DEBUT, lot[0], chaine['debut'], -2.4),
            (SIGNE_FIN, lot[-1], chaine['fin'], 2.4)):
        if not present:
            continue
        x, y = vers_feuille(module['centre'])
        morceaux.append(
            '<text x="%s" y="%s" font-size="5" font-weight="bold" '
            'text-anchor="middle" fill="#ffffff" stroke="%s" '
            'stroke-width="0.35">%s</text>'
            % (_n(x + decalage), _n(y - 0.6), NOIR, signe))
    return morceaux


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
        morceaux.append('<text x="%s" y="%s" font-size="3.2" fill="%s">%s'
                        '</text>' % (_n(x + (6.0 if couleur else 0.0)),
                                     _n(y), NOIR, escape(texte)))
        y += 4.8
    return morceaux, y


def _pied_a4(texte):
    lignes = str(texte or '').split('\n')
    return [('<text x="%s" y="%s" font-size="3" fill="%s">%s</text>'
             % (_n(10.0), _n(FORMAT_A4_MM[1] - 4.0 - 3.6 * rang),
                GRIS_TEXTE, escape(ligne)))
            for rang, ligne in enumerate(lignes) if texte]


def _feuille_de_pan(pan, modules, entrees, pans, pied):
    """Le SVG A4 d'UN pan posé."""
    modules_du_pan = [m for m in modules if m['pan'] == pan['repere']]
    chaines = _chaines_du_pan(modules_du_pan, modules, entrees, pans)
    vers_feuille, echelle = _transformation(
        _etendue_du_pan(pan, modules_du_pan), CADRE_DESSIN_MM)
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
    for chaine in chaines:
        corps += _reperes_de_chaine(chaine, vers_feuille)
    lignes = _colonne_de_legende(chaines, not entrees)
    _verifier_absence_d_argent('\n'.join(t for _c, t in lignes)
                               + LEGENDE_REPERES)
    legende, y = _legende_a4(lignes, COLONNE_X_MM, 28.0)
    corps += legende
    corps.append('<text x="%s" y="%s" font-size="3" fill="%s">%s</text>'
                 % (_n(COLONNE_X_MM), _n(y + 2.0), GRIS_TEXTE,
                    escape(LEGENDE_REPERES)))
    corps.append(_fleche_nord_svg(FORMAT_A4_MM[0] - 16.0, 150.0))
    corps.append(_barre_echelle_svg(COLONNE_X_MM, 182.0, echelle))
    corps += _pied_a4(pied)
    largeur, hauteur = FORMAT_A4_MM
    return ('<svg xmlns="http://www.w3.org/2000/svg" version="1.1" '
            'width="%smm" height="%smm" viewBox="0 0 %s %s">%s</svg>'
            % (_n(largeur), _n(hauteur), _n(largeur), _n(hauteur),
               '\n'.join(corps)))


def svgs_de_pans(roof_layout, affectation, *, pied=''):
    """Les SVG A4, un par pan qui porte au moins un module (liste vide sinon)."""
    from .planche import geometrie_de_planche

    try:
        geometrie = geometrie_de_planche(roof_layout)
    except PlancheRefusee:
        return []
    pans = geometrie.get('pans') or []
    if not any(pan['modules'] for pan in pans):
        return []
    modules, entrees = _plan_des_chaines(roof_layout, affectation)
    return [_feuille_de_pan(pan, modules, entrees, pans, pied)
            for pan in pans if pan['modules']]


def feuilles_de_pans(calepinage, *, moment=None):
    """``(style, pages)`` à passer à ``html_de_planche`` : les règles de page
    A4 et les feuilles de pan, ``('', '')`` quand aucun pan ne porte de
    module. L'affectation est celle du résultat SERVI, jamais recalculée."""
    from .. import selectors

    servi = selectors.resultat_servi(calepinage)
    electrique = (servi or {}).get('electrique') \
        if isinstance(servi, dict) else None
    affectation = list((electrique or {}).get('affectation') or [])
    svgs = svgs_de_pans(getattr(calepinage, 'roof_layout', None),
                            affectation,
                            pied=pied_du_calepinage(calepinage,
                                                    moment=moment))
    if not svgs:
        return '', ''
    return STYLE_FEUILLE_PAN, ''.join(
        '<div class="feuille-pan">%s</div>' % svg for svg in svgs)
