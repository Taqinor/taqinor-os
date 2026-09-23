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
  (``PALETTE_CHAINES`` = ``AFFECTATION_PALETTE`` de ``AffectationChaines.jsx``,
  même ordre de première apparition) : un module a la même couleur sur le
  papier et à l'écran ;
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
L'affectation repère ses modules « <pan>#<rang> » (``services/chaines.py``
``affectation``) : le pan est ``label``, sinon ``id``, sinon ``PAN-<rang de
zone>`` ; le rang compte à partir de 1 dans l'ordre de ``geometry.panels``. Ce
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

import re
from html import escape

from ..planche import PlancheRefusee

__all__ = [
    'CODE_DOCUMENT', 'CHAMP_CHAINAGE', 'PALETTE_CHAINES',
    'COULEUR_NON_AFFECTE', 'SOURCE_MANUELLE', 'MOTS_DE_MONTANT',
    'PlanCablageRefuse', 'rgb_de', 'modules_du_plan', 'plan_de_cablage',
    'lignes_de_legende', 'verifier_legende_sans_montant',
    'svg_de_plan_cablage', 'affectation_du_calepinage',
    'plan_du_calepinage', 'rendre_plan_cablage_svg', 'html_du_plan_cablage',
    'rendre_plan_cablage_pdf', 'exporter_plan_cablage_dxf',
]

#: Le code du document dans l'inventaire (contrat ``calepinage_documents``).
CODE_DOCUMENT = 'plan_cablage'

#: La donnée NOMMÉE quand aucune chaîne n'est publiée — le même champ que
#: l'inventaire des documents déclare pour cette pièce.
CHAMP_CHAINAGE = 'electrique.chainage'

#: La teinte des chaînes — MIROIR EXACT de ``AFFECTATION_PALETTE`` et
#: ``AFFECTATION_UNASSIGNED`` (``AffectationChaines.jsx``, lui-même miroir de
#: la 3D). Un test relit la source JSX : la dérive rougit.
PALETTE_CHAINES = (
    'rgb(36, 130, 214)',   # bleu
    'rgb(232, 125, 33)',   # orange
    'rgb(46, 163, 89)',    # vert
    'rgb(184, 64, 158)',   # magenta
    'rgb(0, 153, 158)',    # sarcelle
    'rgb(212, 61, 71)',    # rouge
    'rgb(115, 102, 199)',  # violet
    'rgb(153, 133, 26)',   # ocre
)
COULEUR_NON_AFFECTE = 'rgb(140, 143, 148)'

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

def _cle_de_pan(zone, rang):
    """Le repère de pan de ``services/chaines.pans_poses`` — même règle."""
    return str(zone.get('label') or zone.get('id') or 'PAN-%d' % rang)


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


def modules_du_plan(roof_layout, geometrie):
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
    modules = []
    for (rang_zone, zone), pan in zip(zones, geometrie.get('pans') or ()):
        cle = _cle_de_pan(zone, rang_zone)
        for rang, centre in zip(_rangs_dessines(zone), pan['modules']):
            modules.append({'module': '%s#%d' % (cle, rang), 'pan': cle,
                            'centre': centre})
    return modules


# ── Le plan : géométrie + affectation, rien de recalculé ───────────────────

def _lignes_lisibles(affectation):
    return [ligne for ligne in (affectation or ())
            if isinstance(ligne, dict) and isinstance(ligne.get('module'), str)]


def plan_de_cablage(roof_layout, affectation):
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

    # Couleurs : ordre de PREMIÈRE APPARITION dans la table, comme l'écran.
    couleurs, legende = {}, []
    par_chaine = {}
    for ligne in lignes:
        chaine = ligne.get('chaine')
        if chaine is None:
            continue
        if chaine not in couleurs:
            couleurs[chaine] = PALETTE_CHAINES[
                len(couleurs) % len(PALETTE_CHAINES)]
            entree = {'chaine': chaine, 'couleur': couleurs[chaine],
                      'modules': 0, 'entrees': [], 'manuels': 0}
            par_chaine[chaine] = entree
            legende.append(entree)
        entree = par_chaine[chaine]
        entree['modules'] += 1
        couple = {'onduleur': ligne.get('onduleur'), 'mppt': ligne.get('mppt')}
        if couple not in entree['entrees']:
            entree['entrees'].append(couple)
        if ligne.get('source') == SOURCE_MANUELLE:
            entree['manuels'] += 1

    table = {ligne['module']: ligne for ligne in lignes}
    modules, dessines = [], set()
    for module in modules_du_plan(roof_layout, geometrie):
        ligne = table.get(module['module']) or {}
        chaine = ligne.get('chaine')
        dessines.add(module['module'])
        modules.append(dict(
            module,
            chaine=chaine,
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


def _lignes_de_chaine(entree):
    titre = 'Chaîne %s — %s' % (entree['chaine'],
                                _pluriel(entree['modules'], 'module'))
    return [titre] + [_texte_entree(e) for e in entree['entrees']]


def lignes_de_legende(plan):
    """Toutes les lignes de texte de la légende, dans l'ordre d'impression."""
    lignes = ['CHAÎNES']
    for entree in plan['legende']:
        lignes.extend(_lignes_de_chaine(entree))
    if plan['manuels']:
        lignes.append('× affectation manuelle : %s'
                      % _pluriel(plan['manuels'], 'module'))
    lignes.append('Non affectés : %s' % _pluriel(plan['non_affectes'],
                                                 'module'))
    if plan['non_dessines']:
        lignes.append('Affectés sans position posée (non dessinés) : %s'
                      % _pluriel(plan['non_dessines'], 'module'))
    return lignes


def verifier_legende_sans_montant(lignes):
    """Refuse une légende qui porterait un mot de montant — en le NOMMANT."""
    trouves = sorted({m.group(0) for ligne in lignes
                      for m in MOTS_DE_MONTANT.finditer(str(ligne))})
    if trouves:
        raise PlanCablageRefuse(
            "Plan de câblage refusé : une pièce de chantier ne porte aucun "
            "montant. Trouvé — %s." % ', '.join(trouves), champ='legende')
    return lignes


# ── Le SVG : la planche de toiture + la couche de câblage ──────────────────

def _coins(centre, module_m):
    demi_l, demi_c = module_m[0] / 2.0, module_m[1] / 2.0
    return ((centre[0] - demi_l, centre[1] - demi_c),
            (centre[0] + demi_l, centre[1] - demi_c),
            (centre[0] + demi_l, centre[1] + demi_c),
            (centre[0] - demi_l, centre[1] + demi_c))


def _forme_de_module(module, vers_feuille, module_m):
    """Un module : teinté par sa chaîne, ou en CONTOUR SEUL s'il n'en a pas."""
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
    if module_m is None:
        # Emprise non SOURCÉE : le module est figuré par son centre, jamais
        # par un rectangle de taille plausible (règle de la planche).
        x, y = vers_feuille(module['centre'])
        return '<circle %s cx="%s" cy="%s" r="0.9" %s />' % (
            attributs, _n(x), _n(y), style)
    points = ' '.join('%s,%s' % tuple(_n(c) for c in vers_feuille(p))
                      for p in _coins(module['centre'], module_m))
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
        lignes = _lignes_de_chaine(entree)

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

    total = sum(hauteur for hauteur, _ in blocs)
    y = FORMAT_A3_MM[1] - MARGE_MM - total + 3.0
    morceaux = ['<g class="legende-cablage">']
    for hauteur, fabrique in blocs:
        morceaux.append(fabrique(y))
        y += hauteur
    morceaux.append('</g>')
    return ''.join(morceaux)


def svg_de_plan_cablage(plan, *, titre='', sous_titre='', pied=''):
    """Le SVG A3 du plan : la planche de TOITURE + la couche de câblage.

    La toiture (contour, pans, obstacles, cotes, nord, échelle, cartouche,
    pied d'empreinte) est celle de ``planche.svg_de_planche`` — contenu
    ``toiture``, qui ne dessine PAS les modules : c'est cette couche qui les
    dessine, teintés par chaîne, avec la MÊME transformation.
    """
    from ..planche import CONTENU_TOITURE, _transformation, svg_de_planche

    verifier_legende_sans_montant(lignes_de_legende(plan))
    geometrie = plan['geometrie']
    base = svg_de_planche(geometrie, titre=titre, sous_titre=sous_titre,
                          pied=pied, contenu=CONTENU_TOITURE)
    vers_feuille, _echelle = _transformation(geometrie['etendue'])
    couche = ['<g class="cablage">']
    for module in plan['modules']:
        couche.append(_forme_de_module(module, vers_feuille,
                                       geometrie.get('module_m')))
    for module in plan['modules']:
        if module['manuel']:
            couche.append(_marque_manuelle(module, vers_feuille))
    couche.append('</g>')
    couche.append(_legende_svg(plan))
    fin = base.rindex('</svg>')
    return base[:fin] + '\n'.join(couche) + '\n' + base[fin:]


# ── Depuis un Calepinage : LIRE l'affectation publiée ──────────────────────

def affectation_du_calepinage(calepinage):
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


def plan_du_calepinage(calepinage, *, affectation=None):
    """Le plan de câblage d'un ``Calepinage`` (affectation LUE si absente)."""
    if affectation is None:
        affectation = affectation_du_calepinage(calepinage)
    return plan_de_cablage(getattr(calepinage, 'roof_layout', None),
                           affectation)


def rendre_plan_cablage_svg(calepinage, *, moment=None, affectation=None):
    """Le SVG du plan de câblage, pied d'empreinte compris (CAL173)."""
    from ..planche import empreinte_du_calepinage

    plan = plan_du_calepinage(calepinage, affectation=affectation)
    return svg_de_plan_cablage(
        plan, titre='Plan de câblage — %s' % calepinage,
        sous_titre='Modules teintés par chaîne (affectation publiée)',
        pied=empreinte_du_calepinage(calepinage, moment=moment))


def html_du_plan_cablage(calepinage, **options):
    """L'UNIQUE mise en page du plan : le PDF et l'aperçu (CALX323) la
    partagent."""
    from ..planche import html_de_planche

    return html_de_planche(rendre_plan_cablage_svg(calepinage, **options))


def rendre_plan_cablage_pdf(calepinage, *, company=None, **options):
    """Octets PDF, via ``core.pdf.render_pdf`` (ARC11) — jamais WeasyPrint."""
    from core.pdf import render_pdf

    return render_pdf(html=html_du_plan_cablage(calepinage, **options),
                      company=company or getattr(calepinage, 'company', None))


def exporter_plan_cablage_dxf(calepinage, *, affectation=None):
    """Le DXF de pose AVEC le calque ``CHAINES`` (``export_dxf``, paramètre
    explicite ``chaines=``)."""
    from ..export_dxf import octets_dxf

    plan = plan_du_calepinage(calepinage, affectation=affectation)
    return octets_dxf(plan['geometrie'], chaines=plan['modules'])
