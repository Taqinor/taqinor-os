"""CALX310 — le PLAN DE CÂBLAGE des chaînes, en PDF et en DXF.

Le constat
==========
L'affectation module → chaîne → entrée MPPT → onduleur est calculée et publiée
(``resultat['electrique']['affectation']``, contrat
``contract_samples/calepinage_resultat.json``) et l'écran la teinte
(``frontend/src/features/calepinage/plan/AffectationChaines.jsx``), mais AUCUNE
pièce imprimable ne la portait : la planche dessine les modules sans
distinction de chaîne (``services/planche.py`` ``_dessin_des_modules``) et le
DXF n'avait que ses quatre calques de pose (``services/export_dxf.py``).

Ce que fait ce module, et ce qu'il ne fait pas
==============================================
* il REPREND la géométrie de la planche (``planche.geometrie_de_planche``) —
  la MÊME projection : le plan de câblage, la planche et le DXF ne peuvent pas
  se contredire ;
* il LIT la table d'affectation PUBLIÉE (``services.electrique
  .resultat_calepinage`` — l'affectation MANUELLE enregistrée y écrase déjà
  l'automatique, CAL234) : jamais une seconde partition recalculée ici, qui
  serait une AUTRE partition que celle qui a été dimensionnée ;
* il TEINTE chaque module par sa chaîne avec la palette de l'écran
  (``PALETTE_CHAINES`` de ``services/chaines.py``, celle que
  ``electrique.affectation[]`` sert — ACAL285 —, même ordre de première
  apparition) : un module a la même couleur sur le papier et à l'écran ;
* un module en affectation MANUELLE (``source: 'affectation manuelle'``) porte
  un signe distinct (×) ;
* un module SANS affectation est dessiné en CONTOUR SEUL, jamais teinté d'une
  chaîne voisine, et compté dans l'encart « non affectés » ;
* la légende liste, chaîne par chaîne, son numéro, son nombre de modules,
  l'onduleur et l'entrée MPPT publiés — un onduleur non attribué par le moteur
  (plusieurs exemplaires, ``onduleur: null``) est dit « non attribué », jamais
  numéroté au hasard ;
* AUCUN MONTANT : la table lue passe le pare-feu des pièces du lot 6
  (``rapport.verifier_etancheite``), et la légende composée est VÉRIFIÉE avant
  rendu (``verifier_legende_sans_montant``).

Le joint entre le document et l'électrique
==========================================
L'affectation repère ses modules « <pan>#<n> » (``services/chaines.py``
``affectation``) : ACAL265 — le pan est sa clé STABLE (``zone.id``, sinon
``PAN-<rang de zone>``, ``production.cle_de_pan``) et ``n`` le numéro stable
du panneau (``panels[].n``), à défaut son rang (1… dans l'ordre de
``geometry.panels``). Ce
module reconstruit EXACTEMENT ces repères pour les modules dessinés
(``modules_du_plan``), y compris quand un panneau illisible n'a pas été
dessiné (le rang des suivants ne glisse pas).

Le refus plutôt que le blanc
============================
Sans géométrie, ``PlancheRefusee`` (champ ``roof_layout``). Sans aucune chaîne
publiée, ``PlanCablageRefuse`` (champ ``electrique.chainage``) : un plan de
câblage sans câblage est une feuille trompeuse.
"""
from __future__ import annotations

import math
import re
import textwrap
from html import escape

from core.electrique.schema_electrique import couleur_de_chaine

from ..planche import PlancheRefusee
from ..tensions_chaines import chaines_servies
from ..chaines import COULEUR_NON_AFFECTE, PALETTE_CHAINES

__all__ = [
    'CODE_DOCUMENT', 'CHAMP_CHAINAGE', 'PALETTE_CHAINES',
    'COULEUR_NON_AFFECTE', 'SOURCE_MANUELLE', 'MOTS_DE_MONTANT',
    'PlanCablageRefuse', 'rgb_de',
    'html_du_plan_cablage',
    'rendre_plan_cablage_pdf', 'exporter_plan_cablage_dxf',
]

#: Le code du document dans l'inventaire (contrat ``calepinage_documents``).
CODE_DOCUMENT = 'plan_cablage'

#: La donnée NOMMÉE quand aucune chaîne n'est publiée — le même champ que
#: l'inventaire des documents déclare pour cette pièce.
CHAMP_CHAINAGE = 'electrique.chainage'

#: La teinte des chaînes — ACAL285 : SOURCE UNIQUE ``services/chaines.py``,
#: celle que ``electrique.affectation[]`` sert ligne par ligne (même palette,
#: même ordre de première apparition : le PDF garde ses teintes).

#: La ``source`` d'une ligne imposée par l'installateur (CAL234).
SOURCE_MANUELLE = 'affectation manuelle'

#: Les mots de montant refusés dans la légende, en JETONS ENTIERS — « marge »
#: y figure : la légende d'un plan de câblage n'a aucune marge géométrique à
#: dire.
MOTS_DE_MONTANT = re.compile(
    r'(?<![\w-])(MAD|DH|prix|coût|cout|montant|remise|marge|TTC|HT)(?![\w-])'
    r'|€', re.IGNORECASE)

_NOIR = '#111111'
_GRIS_TEXTE = '#444444'


class PlanCablageRefuse(PlancheRefusee):
    """Le plan de câblage refuse de sortir, et il NOMME la donnée en cause."""


def rgb_de(couleur):
    """``'rgb(36, 130, 214)'`` -> ``(36, 130, 214)`` (pour le DXF)."""
    return tuple(int(v) for v in re.findall(r'\d+', couleur)[:3])


# ── Le joint document ↔ électrique ─────────────────────────────────────────

def _rangs_dessines(zone):
    """Les rangs (1…n, ordre de ``panels``) des modules que la planche DESSINE.

    Même prédicat que ``planche._modules_du_pan`` : une origine lisible, puis
    chaque panneau ``dict`` aux ``cx``/``cy`` numériques. Un panneau illisible
    n'est pas dessiné mais GARDE son rang — l'affectation le compte.
    """
    from ..planche import _couple, _nombre

    geometrie = zone.get('geometry') \
        if isinstance(zone.get('geometry'), dict) else {}
    panneaux = geometrie.get('panels')
    if not isinstance(panneaux, (list, tuple)):
        return []
    if _couple(geometrie.get('origin'), 'lnglat') is None:
        return []
    return [rang for rang, panneau in enumerate(panneaux, start=1)
            if isinstance(panneau, dict)
            and _nombre(panneau.get('cx')) is not None
            and _nombre(panneau.get('cy')) is not None]


def _modules_du_plan(roof_layout, geometrie):
    """Les modules DESSINÉS, repérés comme l'affectation les nomme.

    ``[{module: '<pan>#<rang>', pan, centre}]`` dans l'ordre du document. Les
    pans de ``geometrie`` sont ceux des zones ``dict`` du document, dans leur
    ordre (``planche._zones``) ; le rang de zone du repère ``PAN-<n>`` compte,
    lui, TOUTES les zones (``chaines.pans_poses``).
    """
    brutes = (roof_layout or {}).get('zones') \
        if isinstance(roof_layout, dict) else None
    zones = [(rang, zone) for rang, zone in enumerate(
        brutes if isinstance(brutes, (list, tuple)) else [], start=1)
        if isinstance(zone, dict)]
    from ..planche import coins_du_module
    from ..production import cle_de_module, cle_de_pan, numeros_des_modules

    modules = []
    for (rang_zone, zone), pan in zip(zones, geometrie.get('pans') or ()):
        # ACAL265 — LA clé de ``chaines.affectation`` : ``zone.id`` et le
        # numéro STABLE du panneau (``panels[].n``), jamais le libellé.
        cle = cle_de_pan(zone, rang_zone)
        numeros = numeros_des_modules(zone.get('geometry'))
        for rang, centre in zip(_rangs_dessines(zone), pan['modules']):
            modules.append({'module': cle_de_module(cle, rang, numeros),
                            'pan': cle,
                            'centre': centre,
                            # ACAL263 — les cotes du module de CE pan.
                            'module_m': pan.get('module_m'),
                            # ACAL605 — l'emprise VRAIE (planche, DXF) ou
                            # ``None`` : le module est alors un cercle.
                            'coins': coins_du_module(pan, centre)})
    return modules


# ── Le plan : géométrie + affectation, rien de recalculé ───────────────────

def _lignes_lisibles(affectation):
    return [ligne for ligne in (affectation or ())
            if isinstance(ligne, dict) and isinstance(ligne.get('module'), str)]


def _plan_de_cablage(roof_layout, affectation):
    """Le plan de câblage, prêt à dessiner — AUCUNE partition recalculée.

    Args:
        roof_layout: le document de conception STOCKÉ.
        affectation: la table PUBLIÉE ``[{module, pan, chaine, onduleur, mppt,
            source}]`` (``resultat['electrique']['affectation']``).

    Returns:
        ``{geometrie, modules, legende, non_affectes, non_dessines, manuels}``
        — ``modules`` porte, par module dessiné, sa ``chaine`` et sa
        ``couleur`` (``None`` pour un module non affecté : jamais la couleur
        d'une chaîne voisine) et ``manuel``.

    Raises:
        PlancheRefusee: aucune géométrie (champ ``roof_layout``).
        PlanCablageRefuse: aucune chaîne publiée (champ
            ``electrique.chainage``).
    """
    from ..planche import geometrie_de_planche

    geometrie = geometrie_de_planche(roof_layout)
    lignes = _lignes_lisibles(affectation)
    if not any(ligne.get('chaine') is not None for ligne in lignes):
        raise PlanCablageRefuse(
            "Plan de câblage impossible : aucune chaîne n'est publiée pour "
            "cette conception. Le plan teinte les modules par la chaîne "
            "RÉELLEMENT dimensionnée — chaînez l'électrique (onglet "
            "Électrique), puis redemandez le plan.",
            champ=CHAMP_CHAINAGE)

    # Couleurs : liées au NUMÉRO de chaîne (S3), comme l'écran ; la légende garde l'ordre d'apparition.
    couleurs, legende = {}, []
    par_chaine = {}
    rangs = {}
    for ligne in lignes:
        chaine = ligne.get('chaine')
        if chaine is None:
            continue
        if chaine not in couleurs:
            couleurs[chaine] = couleur_de_chaine(chaine)
            entree = {'chaine': chaine, 'couleur': couleurs[chaine],
                      'modules': 0, 'entrees': [], 'manuels': 0}
            par_chaine[chaine] = entree
            legende.append(entree)
        entree = par_chaine[chaine]
        entree['modules'] += 1
        # ACAL674 — le n° du module DANS SA CHAÎNE : l'ordre des lignes de
        # l'affectation publiée (1, 2, 3…), jamais un tri.
        rangs[ligne['module']] = entree['modules']
        couple = {'onduleur': ligne.get('onduleur'), 'mppt': ligne.get('mppt')}
        if couple not in entree['entrees']:
            entree['entrees'].append(couple)
        if ligne.get('source') == SOURCE_MANUELLE:
            entree['manuels'] += 1

    table = {ligne['module']: ligne for ligne in lignes}
    modules, dessines = [], set()
    for module in _modules_du_plan(roof_layout, geometrie):
        ligne = table.get(module['module']) or {}
        chaine = ligne.get('chaine')
        dessines.add(module['module'])
        modules.append(dict(
            module,
            chaine=chaine,
            onduleur=ligne.get('onduleur'),
            mppt=ligne.get('mppt'),
            rang=rangs.get(module['module']),
            couleur=couleurs.get(chaine) if chaine is not None else None,
            manuel=ligne.get('source') == SOURCE_MANUELLE))

    # « Non affectés » : tout module, dessiné ou seulement publié, sans chaîne.
    sans_chaine = {m['module'] for m in modules if m['chaine'] is None}
    sans_chaine |= {ligne['module'] for ligne in lignes
                    if ligne.get('chaine') is None}
    non_dessines = sum(1 for ligne in lignes
                       if ligne.get('chaine') is not None
                       and ligne['module'] not in dessines)
    return {
        'geometrie': geometrie,
        'modules': modules,
        'legende': legende,
        'non_affectes': len(sans_chaine),
        'non_dessines': non_dessines,
        'manuels': sum(1 for ligne in lignes
                       if ligne.get('source') == SOURCE_MANUELLE),
    }


# ── La légende : des faits LUS, et aucun montant ───────────────────────────

def _pluriel(nombre, mot):
    return '%d %s%s' % (nombre, mot, '' if nombre in (0, 1) else 's')


def _texte_entree(entree):
    """« onduleur 1 · entrée MPPT 2 » — l'absence DITE, jamais numérotée."""
    onduleur = entree.get('onduleur')
    mppt = entree.get('mppt')
    return '%s · %s' % (
        'onduleur %s' % onduleur if onduleur is not None
        else 'onduleur non attribué',
        'entrée MPPT %s' % mppt if mppt is not None
        else 'entrée MPPT non attribuée')


def _texte_tension(servie):
    """ACAL672 — « Voc à −5 °C : 642,0 V · Isc : 13,9 A », LUS du serveur."""
    voc, froid = servie.get('voc_froid_v'), servie.get('temperature_froide_c')
    if voc is None or froid is None:
        return 'tension non calculée : fiche incomplète'
    texte = 'Voc à %s °C : %s V' % (
        ('%g' % froid).replace('-', '−').replace('.', ','),
        ('%.1f' % voc).replace('.', ','))
    isc = servie.get('isc_a')
    return texte if isc is None else '%s · Isc : %s A' % (
        texte, ('%g' % isc).replace('.', ','))


def _lignes_de_chaine(entree, chaines=None):
    titre = 'Chaîne %s — %s' % (entree['chaine'],
                                _pluriel(entree['modules'], 'module'))
    lignes = [titre] + [_texte_entree(e) for e in entree['entrees']]
    if chaines is not None:
        lignes.append(_texte_tension(chaines.get(entree['chaine']) or {}))
    return lignes


#: ACAL643 — la légende des flèches : le sens de NUMÉROTATION des modules,
#: jamais une polarité (l'ordre électrique d'une chaîne n'est pas publié).
LEGENDE_SENS = 'sens de numérotation — la polarité se vérifie sur site'


def cle_dans_la_chaine(module, repli):
    """ACAL1719 (revue) — la clé d'ordre d'un module DANS SA CHAÎNE : son
    ``rang`` (ACAL674, l'ordre des lignes de l'affectation publiée), celui que
    le DXF publie en attribut ``N`` ; « + » et « − » tombent ainsi sur les
    mêmes modules dans les deux livrables. Sans rang connu : ``repli``."""
    if module.get('rang') is not None:
        return (0, module['rang'])
    return (1,) + tuple(repli)


def bouts_publies(ordonnes, total):
    """``(premier, dernier)`` : le premier module dessiné est-il le rang 1, le
    dernier le rang ``total`` de la chaîne ? Sans rang connu, on garde le
    bout dessiné (comportement d'avant)."""
    premier, dernier = ordonnes[0].get('rang'), ordonnes[-1].get('rang')
    return (premier is None or premier == 1,
            dernier is None or total is None or dernier == total)


def _modules_par_chaine_ordonnes(plan):
    """``{chaîne: [modules…]}`` dessinés, dans l'ordre de la chaîne.

    L'ordre est le rang du module dans sa chaîne (``cle_dans_la_chaine``) ;
    en repli, sans rang : le numéro du repère « <pan>#<n> » dans son pan, les
    pans dans l'ordre du document, et un repère sans numéro lisible garde sa
    position dans le document."""
    pans = {}
    ordonnes = {}
    for position, module in enumerate(plan['modules']):
        if module['chaine'] is None:
            continue
        numero = str(module['module']).rpartition('#')[2]
        pan = pans.setdefault(module['pan'], len(pans))
        ordonnes.setdefault(module['chaine'], []).append(
            (cle_dans_la_chaine(module, (
                pan, int(numero) if numero.isdigit() else position)), module))
    return {chaine: [m for _cle, m in sorted(lot, key=lambda c: c[0])]
            for chaine, lot in ordonnes.items()}


def _totaux_de_chaine(plan):
    return {entree['chaine']: entree['modules'] for entree in plan['legende']}


def _chaines_a_fleche(plan):
    """Les chaînes de plus d'un module dessiné : seules à porter une flèche
    (et la légende du sens) ; rien sans toit dessiné."""
    if not plan['geometrie'].get('etendue'):
        return {}
    return {chaine: modules for chaine, modules
            in _modules_par_chaine_ordonnes(plan).items()
            if len(modules) > 1}


_LISERE = '#ffffff'


def signes_de_bout(premier, dernier, bouts):
    """« + » au-dessus de ``premier`` et « − » au-dessus de ``dernier`` (points
    déjà sur la feuille), chacun seulement si son bout est vrai."""
    from ..planche import _n

    return ''.join(
        '<text x="%s" y="%s" font-size="3.6" font-weight="bold" '
        'text-anchor="middle" fill="%s" stroke="%s" stroke-width="0.5" '
        'paint-order="stroke">%s</text>'
        % (_n(x), _n(y - 1.6), _NOIR, _LISERE, signe)
        for (x, y), signe, imprime in ((premier, '+', bouts[0]),
                                       (dernier, '−', bouts[1]))
        if imprime)


def _fleche_de_chaine(modules, vers_feuille, bouts=(True, True)):
    """ACAL643 / ACAL1719 — la flèche d'une chaîne : une ligne brisée par les
    centres de ses modules, du plus petit au plus grand numéro, en encre
    foncée sur un liseré clair (jamais la teinte des modules qu'elle
    traverse), pointe pleine sur le dernier, « + » au premier et « − » au
    dernier."""
    from ..planche import TRAIT_PAN, _n

    points = [vers_feuille(m['centre']) for m in modules]
    (xa, ya), (xb, yb) = points[-2], points[-1]
    longueur = math.hypot(xb - xa, yb - ya)
    if longueur == 0:
        return ''
    ux, uy = (xb - xa) / longueur, (yb - ya) / longueur
    taille = 2.4
    base = (xb - ux * taille, yb - uy * taille)
    pointe = ' '.join('%s,%s' % (_n(x), _n(y)) for x, y in (
        (xb, yb),
        (base[0] - uy * taille / 2, base[1] + ux * taille / 2),
        (base[0] + uy * taille / 2, base[1] - ux * taille / 2)))
    trace = ' '.join('%s,%s' % (_n(x), _n(y)) for x, y in points)
    bouts = signes_de_bout(points[0], points[-1], bouts)
    return ('<g class="fleche-chaine" data-chaine="%s">'
            '<polyline points="%s" fill="none" stroke="%s" '
            'stroke-width="%s" stroke-linejoin="round" />'
            '<polyline points="%s" fill="none" stroke="%s" '
            'stroke-width="%s" />'
            '<polygon points="%s" fill="%s" stroke="%s" stroke-width="%s" />'
            '%s</g>'
            % (escape(str(modules[0]['chaine']), quote=True),
               trace, _LISERE, _n(TRAIT_PAN * 6), trace, _NOIR,
               _n(TRAIT_PAN * 3), pointe, _NOIR, _LISERE, _n(TRAIT_PAN),
               bouts))


def _lignes_de_legende(plan):
    """Toutes les lignes de texte de la légende, dans l'ordre d'impression."""
    lignes = ['CHAÎNES']
    for entree in plan['legende']:
        lignes.extend(_lignes_de_chaine(entree, plan.get('chaines')))
    if _chaines_a_fleche(plan):
        lignes.append(LEGENDE_SENS)
    if plan['manuels']:
        lignes.append('× affectation manuelle : %s'
                      % _pluriel(plan['manuels'], 'module'))
    lignes.append('Non affectés : %s' % _pluriel(plan['non_affectes'],
                                                 'module'))
    if plan['non_dessines']:
        lignes.append('Affectés sans position posée (non dessinés) : %s'
                      % _pluriel(plan['non_dessines'], 'module'))
    # ACAL673 — la consigne DC de la SOCIÉTÉ, mot pour mot ; vide : rien.
    if plan.get('consigne_dc'):
        lignes.append(plan['consigne_dc'])
    return lignes


def _verifier_legende_sans_montant(lignes):
    """Refuse une légende qui porterait un mot de montant — en le NOMMANT."""
    trouves = sorted({m.group(0) for ligne in lignes
                      for m in MOTS_DE_MONTANT.finditer(str(ligne))})
    if trouves:
        raise PlanCablageRefuse(
            "Plan de câblage refusé : une pièce de chantier ne porte aucun "
            "montant. Trouvé — %s." % ', '.join(trouves), champ='legende')
    return lignes


# ── Le SVG : la planche de toiture + la couche de câblage ──────────────────

def _forme_de_module(module, vers_feuille):
    """Un module : teinté par sa chaîne, ou en CONTOUR SEUL s'il n'en a pas.

    ACAL605 — l'emprise est ``module['coins']`` (``planche.coins_du_module``,
    la même que la planche et le DXF)."""
    from ..planche import TRAIT_MODULE, _n

    affecte = module['chaine'] is not None
    attributs = ('class="%s" data-module="%s" data-chaine="%s"'
                 % ('module-chaine' if affecte else 'module-non-affecte',
                    escape(module['module'], quote=True),
                    escape('' if not affecte else str(module['chaine']),
                           quote=True)))
    if affecte:
        style = ('fill="%s" stroke="%s" stroke-width="%s"'
                 % (module['couleur'], _NOIR, _n(TRAIT_MODULE)))
    else:
        style = ('fill="none" stroke="%s" stroke-width="%s"'
                 % (COULEUR_NON_AFFECTE, _n(TRAIT_MODULE * 2)))
    if module.get('coins') is None:
        # Emprise non SOURCÉE : le module est figuré par son centre, jamais
        # par un rectangle de taille plausible (règle de la planche).
        x, y = vers_feuille(module['centre'])
        return '<circle %s cx="%s" cy="%s" r="0.9" %s />' % (
            attributs, _n(x), _n(y), style)
    points = ' '.join('%s,%s' % tuple(_n(c) for c in vers_feuille(p))
                      for p in module['coins'])
    return '<polygon %s points="%s" %s />' % (attributs, points, style)


def _marque_manuelle(module, vers_feuille):
    """Le signe « × » d'un module en affectation MANUELLE."""
    from ..planche import TRAIT_COTE, _n

    x, y = vers_feuille(module['centre'])
    d = 0.8
    return ('<g class="marque-manuelle" data-module="%s">'
            '<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s" '
            'stroke-width="%s" />'
            '<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s" '
            'stroke-width="%s" /></g>'
            % (escape(module['module'], quote=True),
               _n(x - d), _n(y - d), _n(x + d), _n(y + d), _NOIR,
               _n(TRAIT_COTE), _n(x - d), _n(y + d), _n(x + d), _n(y - d),
               _NOIR, _n(TRAIT_COTE)))


#: Interlignes de la légende de câblage (mm).
_PAS_TITRE = 4.8
_PAS_SOUS_LIGNE = 3.8


def _legende_svg(plan):
    """La légende des chaînes, ANCRÉE EN BAS du bandeau latéral.

    Le haut du bandeau porte la légende de toiture et les orientations de la
    planche : ancrer ce bloc en bas évite qu'il ne les recouvre.
    """
    from ..planche import (
        FORMAT_A3_MM, LARGEUR_BANDEAU_MM, MARGE_MM, _n,
    )

    x = FORMAT_A3_MM[0] - MARGE_MM - LARGEUR_BANDEAU_MM + 3.0
    blocs = []  # (hauteur, fabrique(y) -> svg)

    def titre(texte, gras=True):
        def fabrique(y):
            return ('<text x="%s" y="%s" font-size="3.6"%s fill="%s">%s'
                    '</text>' % (_n(x), _n(y),
                                 ' font-weight="bold"' if gras else '',
                                 _NOIR, escape(texte)))
        return (_PAS_TITRE, fabrique)

    blocs.append(titre('CHAÎNES'))
    for entree in plan['legende']:
        lignes = _lignes_de_chaine(entree, plan.get('chaines'))

        def chaine(y, entree=entree, lignes=lignes):
            morceaux = [
                '<g class="legende-chaine" data-chaine="%s">'
                % escape(str(entree['chaine']), quote=True),
                '<rect x="%s" y="%s" width="4" height="3" fill="%s" '
                'stroke="%s" stroke-width="0.2" />'
                % (_n(x), _n(y - 2.4), entree['couleur'], _NOIR),
                '<text x="%s" y="%s" font-size="3.2" fill="%s">%s</text>'
                % (_n(x + 6.0), _n(y), _NOIR, escape(lignes[0]))]
            for rang, texte in enumerate(lignes[1:], start=1):
                morceaux.append(
                    '<text x="%s" y="%s" font-size="2.8" fill="%s">%s</text>'
                    % (_n(x + 6.0), _n(y + rang * _PAS_SOUS_LIGNE),
                       _GRIS_TEXTE, escape(texte)))
            morceaux.append('</g>')
            return ''.join(morceaux)
        blocs.append((_PAS_TITRE + _PAS_SOUS_LIGNE * (len(lignes) - 1),
                      chaine))

    if _chaines_a_fleche(plan):
        def sens(y):
            return ('<text class="legende-sens" x="%s" y="%s" '
                    'font-size="3.2" fill="%s">%s</text>'
                    % (_n(x), _n(y), _GRIS_TEXTE, escape(LEGENDE_SENS)))
        blocs.append((_PAS_SOUS_LIGNE + 1.0, sens))

    if plan['manuels']:
        texte_manuel = ('× affectation manuelle : %s'
                        % _pluriel(plan['manuels'], 'module'))
        blocs.append(titre(texte_manuel, gras=False))

    encart = ['Non affectés : %s' % _pluriel(plan['non_affectes'], 'module')]
    if plan['non_dessines']:
        encart.append('Affectés sans position posée : %s'
                      % _pluriel(plan['non_dessines'], 'module'))
    hauteur_encart = 3.0 + _PAS_TITRE * len(encart)

    def encart_svg(y):
        morceaux = [
            '<g class="encart-non-affectes">',
            '<rect x="%s" y="%s" width="%s" height="%s" fill="none" '
            'stroke="%s" stroke-width="0.3" />'
            % (_n(x - 1.0), _n(y - 3.8), _n(LARGEUR_BANDEAU_MM - 6.0),
               _n(hauteur_encart), COULEUR_NON_AFFECTE)]
        for rang, texte in enumerate(encart):
            morceaux.append(
                '<text x="%s" y="%s" font-size="3.2" fill="%s">%s</text>'
                % (_n(x + 1.0), _n(y + rang * _PAS_TITRE), _NOIR,
                   escape(texte)))
        morceaux.append('</g>')
        return ''.join(morceaux)
    blocs.append((hauteur_encart + 2.0, encart_svg))

    consigne = textwrap.wrap(plan.get('consigne_dc') or '', 44)
    if consigne:
        def consigne_svg(y):
            return ('<text class="consigne-dc" x="%s" y="%s" '
                    'font-size="2.8" fill="%s">%s</text>' % (
                        _n(x), _n(y), _NOIR, ''.join(
                            '<tspan x="%s" dy="%s">%s</tspan>' % (
                                _n(x), '0' if rang == 0 else _n(3.4),
                                escape(ligne))
                            for rang, ligne in enumerate(consigne))))
        blocs.append((3.4 * len(consigne) + 2.0, consigne_svg))

    total = sum(hauteur for hauteur, _ in blocs)
    y = FORMAT_A3_MM[1] - MARGE_MM - total + 3.0
    morceaux = ['<g class="legende-cablage">']
    for hauteur, fabrique in blocs:
        morceaux.append(fabrique(y))
        y += hauteur
    morceaux.append('</g>')
    return ''.join(morceaux)


def _svg_de_plan_cablage(plan, *, titre='', sous_titre='', pied=''):
    """Le SVG A3 du plan : la planche de TOITURE + la couche de câblage.

    La toiture (contour, pans, obstacles, cotes, nord, échelle, cartouche,
    pied d'empreinte) est celle de ``planche.svg_de_planche`` — contenu
    ``toiture``, qui ne dessine PAS les modules : c'est cette couche qui les
    dessine, teintés par chaîne, avec la MÊME transformation.
    """
    from ..planche import (
        CONTENU_TOITURE, DEBUT_FEUILLE, FIN_FEUILLE, _transformation,
        svg_de_planche,
    )

    _verifier_legende_sans_montant(_lignes_de_legende(plan))
    geometrie = plan['geometrie']
    base = svg_de_planche(geometrie, titre=titre, sous_titre=sous_titre,
                          pied=pied, contenu=CONTENU_TOITURE)
    couche = ['<g class="cablage">']
    # ACAL260 — sans toit dessiné (champ au sol seul), aucun module de toit à
    # teinter : la légende des chaînes reste, sur la première feuille.
    if geometrie.get('etendue'):
        vers_feuille, _echelle = _transformation(geometrie['etendue'])
        for module in plan['modules']:
            couche.append(_forme_de_module(module, vers_feuille))
        for module in plan['modules']:
            if module['manuel']:
                couche.append(_marque_manuelle(module, vers_feuille))
        totaux = _totaux_de_chaine(plan)
        for chaine, modules in _chaines_a_fleche(plan).items():
            couche.append(_fleche_de_chaine(
                modules, vers_feuille,
                bouts_publies(modules, totaux.get(chaine))))
    couche.append('</g>')
    couche.append(_legende_svg(plan))
    # ACAL260 — un SVG empilé (toit + surfaces de pose) reçoit la couche dans
    # SA PREMIÈRE feuille (celle du toit), dont elle partage le repère.
    fin = -1
    if DEBUT_FEUILLE in base:
        fin = base.find('</svg>\n' + FIN_FEUILLE)
    if fin == -1:
        fin = base.rindex('</svg>')
    return base[:fin] + '\n'.join(couche) + '\n' + base[fin:]


# ── Depuis un Calepinage : LIRE l'affectation publiée ──────────────────────

def _affectation_publiee_du_calepinage(calepinage):
    """La table d'affectation PUBLIÉE par ``GET resultat/`` — jamais recalculée.

    Elle passe le pare-feu des pièces du lot 6 (``rapport
    .verifier_etancheite``) : une grandeur de coût la fait refuser, nommée.
    """
    from ..electrique import TemperaturesInvalides, resultat_calepinage
    from ..rapport import verifier_etancheite

    try:
        servi = resultat_calepinage(calepinage)
    except TemperaturesInvalides as refus:
        raise PlanCablageRefuse(
            str(refus), champ=getattr(refus, 'champ', '') or 'temperatures'
        ) from refus
    electrique = (servi or {}).get('electrique') \
        if isinstance(servi, dict) else None
    affectation = list((electrique or {}).get('affectation') or [])
    verifier_etancheite(affectation, origine='electrique.affectation')
    return affectation


def _plan_du_calepinage(calepinage, *, affectation=None):
    """Le plan de câblage d'un ``Calepinage`` (affectation LUE si absente)."""
    publiee = affectation is None
    if publiee:
        affectation = _affectation_publiee_du_calepinage(calepinage)
    plan = _plan_de_cablage(getattr(calepinage, 'roof_layout', None),
                            affectation)
    plan['consigne_dc'] = _consigne_dc_de_societe(calepinage)
    if publiee:
        # ACAL672 — les tensions SERVIES (``evaluer-electrique``), rien de
        # recalculé ici.
        plan['chaines'] = chaines_servies(calepinage)
    return plan


def _consigne_dc_de_societe(calepinage):
    """ACAL673 — la phrase que la SOCIÉTÉ a saisie dans ses réglages
    (``electrique_societe.consigne_dc_plan_cablage``), ``''`` si vide : le
    logiciel n'écrit jamais lui-même une consigne de sécurité."""
    from ... import selectors

    reglages = selectors.parametres_de_societe(
        getattr(calepinage, 'company', None))
    entree = (reglages.get('electrique_societe') or {}).get(
        'consigne_dc_plan_cablage')
    valeur = entree.get('valeur') if isinstance(entree, dict) else None
    texte = valeur.get('texte') if isinstance(valeur, dict) else None
    return texte.strip() if isinstance(texte, str) else ''


def _rendre_plan_cablage_svg(calepinage, *, moment=None, affectation=None):
    """Le SVG du plan de câblage, pied d'empreinte compris (CAL173)."""
    from ..planche import pied_du_calepinage

    plan = _plan_du_calepinage(calepinage, affectation=affectation)
    return _svg_de_plan_cablage(
        plan, titre='Plan de câblage — %s' % calepinage,
        sous_titre='Modules teintés par chaîne (affectation publiée)',
        pied=pied_du_calepinage(calepinage, moment=moment))


def html_du_plan_cablage(calepinage, *, langue=None, **options):
    """L'UNIQUE mise en page du plan : le PDF et l'aperçu (CALX323) la
    partagent. ``langue`` est accepté pour la forme commune des mises en
    page (l'aperçu la transmet à toutes) : ce plan n'est servi qu'en
    français."""
    from ..planche import html_de_planche

    return html_de_planche(_rendre_plan_cablage_svg(calepinage, **options))


def rendre_plan_cablage_pdf(calepinage, *, company=None, **options):
    """Octets PDF, via ``core.pdf.render_pdf`` (ARC11) — jamais WeasyPrint."""
    from core.pdf import render_pdf

    return render_pdf(html=html_du_plan_cablage(calepinage, **options),
                      company=company or getattr(calepinage, 'company', None))


def exporter_plan_cablage_dxf(calepinage, *, affectation=None):
    """Le DXF de pose AVEC le calque ``CHAINES`` (``export_dxf``, paramètre
    explicite ``chaines=``) — et, CALX314, le calque ``PROVENANCE``."""
    from ..export_dxf import octets_dxf
    from ..provenance_document import lignes_de_provenance

    plan = _plan_du_calepinage(calepinage, affectation=affectation)
    return octets_dxf(plan['geometrie'], chaines=plan['modules'],
                      provenance=lignes_de_provenance(calepinage))
