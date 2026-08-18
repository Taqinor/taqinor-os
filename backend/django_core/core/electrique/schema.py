# -*- coding: utf-8 -*-
"""PV39 — SCHÉMA UNIFILAIRE v2 : la chaîne canonique, dessinée depuis le calcul.

Le brouillon de première génération
(``apps/ventes/single_line_diagram.py``) dessinait cinq blocs FIXES — Panneaux →
Strings → Onduleur → Comptage → ONEE — décidés à partir d'un dict d'étiquettes.
Il ne pouvait donc pas mentir sur les protections : il n'en parlait pas. Cette
version-ci dessine la chaîne CANONIQUE d'un dossier de raccordement :

    Panneaux (N × M) → [fusibles gPV] → coffret DC → [parafoudre DC] →
    sectionneur DC → onduleur (une amorce par entrée MPPT) → [branche batterie]
    → disjoncteur AC → parafoudre AC → [DDR type A] → compteur de production →
    TGBT → compteur ONEE / injection

Les blocs entre crochets n'apparaissent QUE si la règle correspondante les a
retenus (PV35) : un schéma qui montre un parafoudre absent du bordereau est un
schéma qu'un bureau de contrôle prend en défaut. Le tableau d'équipements dessiné
à côté est généré depuis les MÊMES listes ``protections[]`` / ``cables[]`` que le
bordereau — un test l'arme (le contenu du tableau EST la liste des protections).

Format A4 paysage par défaut ; au-delà du seuil de largeur (chaîne trop longue
pour trois rangées utiles), bascule en A3 paysage. Le ``viewBox`` est FIXE pour
un format donné : deux schémas du même format se superposent au pixel près.

Aucun prix, aucun montant : uniquement des grandeurs électriques et des repères.
"""

from dataclasses import dataclass
from html import escape

from core.electrique.types import fr

__all__ = [
    "FORMAT_A4_PAYSAGE", "FORMAT_A3_PAYSAGE", "RANGEES_MAX_A4",
    "Bloc", "blocs_du_schema", "lignes_tableau", "rendre_schema",
]

#: Formats de planche, en pixels CSS à 96 ppp (A4 paysage 297 × 210 mm,
#: A3 paysage 420 × 297 mm). Le viewBox est fixe pour un format donné.
FORMAT_A4_PAYSAGE = (1122.0, 794.0)
FORMAT_A3_PAYSAGE = (1587.0, 1122.0)

#: Au-delà de ce nombre de rangées à la largeur utile A4, la planche passe en A3.
#: Trois rangées de quatre organes couvrent la chaîne canonique complète (champ →
#: compteur ONEE, batterie comprise) : une installation courante reste donc en A4,
#: et seul un dossier à chaîne longue (plusieurs onduleurs, organes additionnels)
#: réclame l'A3.
RANGEES_MAX_A4 = 3

_MARGE = 28.0
_BLOC_L = 132.0
_BLOC_H = 68.0
#: Longueurs de texte qui TIENNENT dans une boîte de 132 px : ~6 px par caractère
#: à la taille du titre (12), ~4,5 px à celle du détail (9). Le SVG ne coupe pas
#: un texte trop long, il le laisse déborder sur le voisin.
_CARACTERES_TITRE = 22
_CARACTERES_SOUS_TITRE = 28
_LIGNES_SOUS_TITRE = 2
_ECART = 34.0
_PAS = _BLOC_L + _ECART
_RANGEE_H = 116.0
#: Géométrie de la pointe de flèche (cf. ``_pointe``) et DÉGAGEMENT qu'elle
#: réclame devant elle : sa hauteur, PLUS autant de trait droit. En dessous, la
#: pointe se confond avec le coin d'équerre ou le trait qui la précède — on ne
#: lit plus une flèche, on lit un trait qui s'arrête. C'est le dégagement que
#: ``_liaison`` s'accorde depuis toujours entre deux rangées, et la référence de
#: tout le dessin : aucune pointe ne doit être émise avec moins.
_POINTE_H = 9.0
_POINTE_L = 5.0
_DEGAGEMENT_POINTE = 2 * _POINTE_H
_BRANCHE_DX = 30.0
#: Hauteur de l'équerre de raccordement d'une branche (sous la gouttière terre).
_BRANCHE_EQUERRE_DY = 26.0
#: Profondeur de la branche sous son porteur — DÉRIVÉE, jamais posée à la main.
#: L'équerre tombe à ``_BLOC_H + _BRANCHE_EQUERRE_DY`` sous le haut du porteur ;
#: il faut ENSUITE ``_DEGAGEMENT_POINTE`` avant la boîte de la branche. La
#: valeur écrite en dur (96) n'en laissait que 2 : l'équerre était tracée DANS
#: la pointe de 9 px, et la flèche onduleur → batterie n'existait plus à l'œil.
_BRANCHE_DY = _BLOC_H + _BRANCHE_EQUERRE_DY + _DEGAGEMENT_POINTE
#: Gouttière entre le bas d'une branche et la rangée suivante.
_ECART_SOUS_BRANCHE = 12.0
#: Rangée agrandie quand une BRANCHE pend sous un organe (parc batterie) : elle
#: loge la branche ENTIÈRE, sinon la rangée suivante se pose sur la batterie.
_RANGEE_H_AVEC_BRANCHE = _BRANCHE_DY + _BLOC_H + _ECART_SOUS_BRANCHE
#: Hauteur de la gouttière où circulent les liaisons de terre, entre le bas d'un
#: bloc et le haut de ce qui suit (branche batterie comprise).
_GOUTTIERE_DY = 14.0
_TABLEAU_L = 340.0
_TRAIT = "#1f3a5f"
_TEXTE_SECONDAIRE = "#555555"
#: Interligne et retrait des étiquettes d'amorce MPPT, posées dans la
#: gouttière AU-DESSUS du bloc onduleur (cf. ``_amorces_mppt``).
_ETIQUETTE_H = 10.0
_ETIQUETTE_DY = 6.0
#: Haut de la zone de dessin : juste sous le titre et le sous-titre de planche
#: — mais l'en-tête ne court que sur ``_LARGEUR_ENTETE`` px depuis la marge
#: gauche, au-delà desquels une étiquette peut remonter jusqu'à la marge.
_PLAFOND_DESSIN = _MARGE + 38.0
_LARGEUR_ENTETE = 380.0

#: Teinte par famille de bloc (tuple de paires : aucune globale mutable).
_TEINTES = (
    ("champ", "#fff7e6"),
    ("fusibles", "#eef6ff"),
    ("coffret_dc", "#eef6ff"),
    ("parafoudre_dc", "#eef6ff"),
    ("sectionneur_dc", "#eef6ff"),
    ("onduleur", "#e9f7ef"),
    ("batterie", "#fff0f3"),
    ("disjoncteur_ac", "#f3eefb"),
    ("parafoudre_ac", "#f3eefb"),
    ("ddr", "#f3eefb"),
    ("compteur_production", "#f3eefb"),
    ("tgbt", "#f3eefb"),
    ("reseau", "#fdeeee"),
)

#: Blocs reliés à la barrette de terre unique.
_A_LA_TERRE = ("champ", "onduleur", "tgbt")

#: Organes dessinés EN BRANCHE (hors chaîne série) et l'organe qui les porte.
_EN_BRANCHE = ("batterie",)
_ANCRE_DE_BRANCHE = "onduleur"


@dataclass(frozen=True)
class Bloc:
    """Un bloc du schéma : sa clef stable, son titre, sa ligne de détail."""

    clef: str
    titre: str
    sous_titre: str = ""


def _esc(texte):
    return escape(str(texte if texte is not None else ""), quote=True)


def _teinte(clef):
    for nom, couleur in _TEINTES:
        if nom == clef:
            return couleur
    return "#ffffff"


def _protection(resultat, repere):
    for protection in resultat.protections:
        if protection.repere == repere:
            return protection
    return None


# ─────────────────────────────────────────────────────── chaîne canonique
def blocs_du_schema(entree, resultat):
    """La chaîne canonique, RÉDUITE aux organes réellement retenus."""
    blocs = []
    chaines = resultat.chaines
    nb_chaines = len(chaines)
    longueurs = sorted({c.nb_modules for c in chaines})
    if nb_chaines:
        detail = ("%d × %d modules" % (nb_chaines, longueurs[0])
                  if len(longueurs) == 1
                  else "%d chaînes de %s modules"
                       % (nb_chaines, " / ".join(str(v) for v in longueurs)))
    else:
        detail = "aucune chaîne"
    blocs.append(Bloc("champ", entree.module.designation or "Champ PV",
                      "%d modules · %s Wc · %s"
                      % (entree.nb_modules, fr(entree.module.pmax_wc, 0),
                         detail)))

    fusible = _protection(resultat, "F1")
    if fusible is not None:
        blocs.append(Bloc("fusibles", "Fusibles gPV",
                          "%d × %s" % (fusible.quantite, fusible.calibre)))
    if nb_chaines:
        blocs.append(Bloc("coffret_dc", "Coffret DC",
                          "%d chaîne(s) raccordée(s)" % nb_chaines))
    parafoudre_dc = _protection(resultat, "PDC1")
    if parafoudre_dc is not None:
        blocs.append(Bloc("parafoudre_dc", "Parafoudre DC Type 2",
                          parafoudre_dc.calibre))
    sectionneur = _protection(resultat, "QDC1")
    if sectionneur is not None:
        blocs.append(Bloc("sectionneur_dc", "Sectionneur DC",
                          sectionneur.calibre))

    onduleur = entree.onduleur
    detail_onduleur = [
        "%s kW" % fr(onduleur.ac_kw, 1),
        "triphasé" if int(entree.phases or 1) == 3 else "monophasé",
        "%d entrée(s) MPPT" % max(1, onduleur.n_mppt),
    ]
    if onduleur.rendement_euro_pct:
        # Publié SEULEMENT quand une fiche le donne (cf. SpecOnduleur).
        detail_onduleur.append("η %s %%"
                               % fr(onduleur.rendement_euro_pct, 1))
    blocs.append(Bloc("onduleur", onduleur.designation or "Onduleur",
                      " · ".join(detail_onduleur)))
    if entree.batterie:
        blocs.append(Bloc("batterie",
                          entree.batterie_designation or "Batterie",
                          _detail_batterie(entree)))

    disjoncteur = _protection(resultat, "QAC1")
    if disjoncteur is not None:
        blocs.append(Bloc("disjoncteur_ac", "Disjoncteur AC",
                          disjoncteur.calibre))
    parafoudre_ac = _protection(resultat, "PAC1")
    if parafoudre_ac is not None:
        blocs.append(Bloc("parafoudre_ac", "Parafoudre AC Type 2",
                          parafoudre_ac.calibre))
    ddr = _protection(resultat, "DDR1")
    if ddr is not None:
        blocs.append(Bloc("ddr", "Différentiel type A", ddr.calibre))

    if disjoncteur is not None:
        blocs.append(Bloc("compteur_production", "Compteur de production",
                          "énergie produite"))
        blocs.append(Bloc("tgbt", "TGBT",
                          _conducteurs_texte(entree)))
        blocs.append(Bloc("reseau", "Compteur ONEE",
                          "injection / soutirage"))
    return tuple(blocs)


def _detail_batterie(entree):
    """« 10,2 kWh · 51,2 V » — ce qu'on SAIT du parc, sinon rien d'inventé."""
    morceaux = []
    if entree.batterie_kwh:
        morceaux.append("%s kWh" % fr(entree.batterie_kwh, 1))
    if entree.batterie_v_nominal:
        morceaux.append("%s V" % fr(entree.batterie_v_nominal, 1))
    return " · ".join(morceaux) if morceaux else "stockage DC"


def _conducteurs_texte(entree):
    """Variante mono / tri : ce sont les CONDUCTEURS qui changent, pas le dessin."""
    if int(entree.phases or 1) == 3:
        return "3P + N + T · 400 V"
    return "P + N + T · 230 V"


# ─────────────────────────────────────────────────── tableau d'équipements
def lignes_tableau(resultat):
    """Le tableau d'équipements — MÊME source que le bordereau.

    Une ligne par protection retenue, puis une par câble dimensionné :
    ``(repère, désignation, calibre ou section, quantité)``.
    """
    lignes = []
    for protection in resultat.protections:
        lignes.append((protection.repere, protection.designation,
                       protection.calibre, "%d u" % protection.quantite))
    for cable in resultat.cables:
        lignes.append((cable.repere, cable.designation,
                       "%s mm²" % fr(cable.section_mm2, 1),
                       "%s m" % fr(cable.longueur_m * cable.nb_conducteurs, 1)))
    return tuple(lignes)


# ─────────────────────────────────────────────────────────────── géométrie
def _format_planche(nb_blocs):
    """A4 par défaut ; A3 dès que la chaîne déborde de deux rangées utiles."""
    par_rangee_a4 = _blocs_par_rangee(FORMAT_A4_PAYSAGE[0])
    rangees_a4 = _rangees(nb_blocs, par_rangee_a4)
    if rangees_a4 <= RANGEES_MAX_A4:
        return FORMAT_A4_PAYSAGE
    return FORMAT_A3_PAYSAGE


def _blocs_par_rangee(largeur_planche):
    utile = largeur_planche - 2 * _MARGE - _TABLEAU_L - _ECART
    return max(1, int((utile + _ECART) // _PAS))


def _rangees(nb_blocs, par_rangee):
    if nb_blocs <= 0:
        return 0
    return -(-nb_blocs // par_rangee)      # division entière par excès


def _positions(blocs, largeur_planche, positions_forcees=None):
    """Serpentin BOUSTROPHÉDON : chaque rangée repart dans l'autre sens.

    Le retour à la ligne devient une simple descente verticale au même x, au
    lieu d'un long trait qui traverse la rangée précédente — sur un schéma
    unifilaire, un trait qui recoupe le dessin se lit comme une liaison.

    Les organes de ``_EN_BRANCHE`` (le parc batterie) sortent du serpentin : ils
    ne sont pas EN SÉRIE dans la chaîne, ils PENDENT sous l'onduleur (côté DC).
    Les dessiner entre l'onduleur et le disjoncteur ferait croire que l'énergie
    traverse la batterie pour aller au réseau. La rangée s'agrandit alors pour
    loger la branche sans que la rangée suivante ne vienne dessus.

    ``positions_forcees`` (``{clef: {"x": .., "y": ..}}``) écrase la position
    calculée d'un bloc, clef par clef : c'est la porte de sortie quand un
    dessinateur veut recaler UN organe sans réécrire le moteur.

    Chaque position est ``(bloc, x, y, rangée, en_branche)``.
    """
    par_rangee = _blocs_par_rangee(largeur_planche)
    forcees = positions_forcees or {}
    en_branche = tuple(b for b in blocs if b.clef in _EN_BRANCHE)
    rangee_h = _RANGEE_H_AVEC_BRANCHE if en_branche else _RANGEE_H
    calculees = []
    for index, bloc in enumerate(b for b in blocs if b.clef not in _EN_BRANCHE):
        rangee, colonne = divmod(index, par_rangee)
        if rangee % 2:                      # rangée impaire : de droite à gauche
            colonne = par_rangee - 1 - colonne
        x = _MARGE + colonne * _PAS
        y = _MARGE + 54.0 + rangee * rangee_h
        forcee = forcees.get(bloc.clef) or {}
        calculees.append((
            bloc,
            float(forcee.get("x", x)),
            float(forcee.get("y", y)),
            rangee,
            False,
        ))
    ancre = next((place for place in calculees
                  if place[0].clef == _ANCRE_DE_BRANCHE), None)
    for bloc in en_branche:
        x, y = _position_de_branche(ancre, calculees, largeur_planche)
        forcee = forcees.get(bloc.clef) or {}
        calculees.append((
            bloc,
            float(forcee.get("x", x)),
            float(forcee.get("y", y)),
            ancre[3] if ancre else 0,
            True,
        ))
    return tuple(calculees)


def _position_de_branche(ancre, places, largeur_planche):
    """Place la branche À CÔTÉ de l'aplomb de son porteur, jamais dessous.

    L'aplomb du porteur est déjà pris : c'est par là que le serpentin redescend
    vers la rangée suivante quand le porteur termine une rangée. Une branche
    posée là serait traversée par la liaison série — le lecteur y verrait un
    organe EN SÉRIE. On la décale donc à gauche (à droite si le bord gauche est
    atteint), et on ne retombe à l'aplomb qu'en dernier recours.
    """
    if ancre is None:
        return (_MARGE, _MARGE + 54.0)
    y = ancre[2] + _BRANCHE_DY
    utile = largeur_planche - _MARGE - _TABLEAU_L - _ECART
    candidats = (ancre[1] - _BLOC_L - _BRANCHE_DX,
                 ancre[1] + _BLOC_L + _BRANCHE_DX,
                 ancre[1])
    for x in candidats:
        if x < _MARGE or x + _BLOC_L > utile:
            continue
        if not _chevauche(x, y, places):
            return (x, y)
    return (ancre[1], y)


def _chevauche(x, y, places):
    for place in places:
        if (x < place[1] + _BLOC_L and place[1] < x + _BLOC_L
                and y < place[2] + _BLOC_H and place[2] < y + _BLOC_H):
            return True
    return False


# ─────────────────────────────────────────────────────────────── primitives
def _bloc_svg(x, y, bloc):
    cx = x + _BLOC_L / 2
    parties = [
        '<rect x="%s" y="%s" width="%s" height="%s" rx="6" fill="%s" '
        'stroke="%s" stroke-width="2"/>'
        % (_n(x), _n(y), _n(_BLOC_L), _n(_BLOC_H), _teinte(bloc.clef), _TRAIT),
        '<text x="%s" y="%s" text-anchor="middle" font-size="12" '
        'font-weight="600" fill="%s">%s</text>'
        % (_n(cx), _n(y + 22), _TRAIT, _esc(_tronquer(bloc.titre,
                                                      _CARACTERES_TITRE))),
    ]
    for rang, ligne in enumerate(_lignes_sous_titre(bloc.sous_titre)):
        parties.append(
            '<text x="%s" y="%s" text-anchor="middle" font-size="9" '
            'fill="%s">%s</text>'
            % (_n(cx), _n(y + 38 + rang * 13), _TEXTE_SECONDAIRE, _esc(ligne)))
    return "".join(parties)


def _lignes_sous_titre(texte):
    """Découpe la ligne de détail sur ses séparateurs pour TENIR dans la boîte.

    Un texte plus large que sa boîte déborde sur ses voisins (le SVG ne coupe
    pas tout seul) : on répartit donc sur deux lignes au maximum, en coupant aux
    séparateurs « · » plutôt qu'au milieu d'une valeur.
    """
    texte = (texte or "").strip()
    if not texte:
        return ()
    if len(texte) <= _CARACTERES_SOUS_TITRE:
        return (texte,)
    morceaux = texte.split(" · ")
    lignes = []
    courante = ""
    for morceau in morceaux:
        candidate = ("%s · %s" % (courante, morceau)) if courante else morceau
        if len(candidate) <= _CARACTERES_SOUS_TITRE or not courante:
            courante = candidate
        else:
            lignes.append(courante)
            courante = morceau
        if len(lignes) == _LIGNES_SOUS_TITRE:
            break
    if len(lignes) < _LIGNES_SOUS_TITRE and courante:
        lignes.append(courante)
    return tuple(_tronquer(ligne, _CARACTERES_SOUS_TITRE) for ligne in lignes)


def _n(valeur):
    """Coordonnée SVG : au dixième, séparateur POINT (le SVG n'est pas français)."""
    return ("%.1f" % float(valeur)).rstrip("0").rstrip(".")


def _trait(x1, y1, x2, y2, pointille=False):
    style = ' stroke-dasharray="4 3"' if pointille else ""
    return ('<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s" '
            'stroke-width="2"%s/>'
            % (_n(x1), _n(y1), _n(x2), _n(y2), _TRAIT, style))


def _pointe(x, y, direction):
    """Pointe de flèche orientée (``droite``, ``gauche``, ``bas``).

    Elle occupe ``_POINTE_H`` px EN AMONT du point visé : tout appelant doit lui
    laisser ce dégagement (``_DEGAGEMENT_POINTE``), sans quoi elle est dessinée
    sous le trait qui la précède et disparaît sans qu'aucune sortie ne manque.
    """
    if direction == "droite":
        points = "%s,%s %s,%s %s,%s" % (
            _n(x), _n(y), _n(x - _POINTE_H), _n(y - _POINTE_L),
            _n(x - _POINTE_H), _n(y + _POINTE_L))
    elif direction == "gauche":
        points = "%s,%s %s,%s %s,%s" % (
            _n(x), _n(y), _n(x + _POINTE_H), _n(y - _POINTE_L),
            _n(x + _POINTE_H), _n(y + _POINTE_L))
    else:
        points = "%s,%s %s,%s %s,%s" % (
            _n(x), _n(y), _n(x - _POINTE_L), _n(y - _POINTE_H),
            _n(x + _POINTE_L), _n(y - _POINTE_H))
    return '<polygon points="%s" fill="%s"/>' % (points, _TRAIT)


def _liaison(depart, arrivee):
    """Relie deux blocs : flèche droite/gauche dans la rangée, descente sinon."""
    _bloc_a, xa, ya, rangee_a = depart[:4]
    _bloc_b, xb, yb, rangee_b = arrivee[:4]
    milieu_a, milieu_b = ya + _BLOC_H / 2, yb + _BLOC_H / 2
    if rangee_a == rangee_b:
        if xb >= xa:
            return (_trait(xa + _BLOC_L, milieu_a, xb - _POINTE_H, milieu_b)
                    + _pointe(xb, milieu_b, "droite"))
        return (_trait(xa, milieu_a, xb + _BLOC_L + _POINTE_H, milieu_b)
                + _pointe(xb + _BLOC_L, milieu_b, "gauche"))
    centre_a, centre_b = xa + _BLOC_L / 2, xb + _BLOC_L / 2
    # Le coude se pose UN dégagement complet au-dessus de la boîte visée : la
    # pointe garde ses 9 px, précédés d'autant de trait droit.
    coude = yb - _DEGAGEMENT_POINTE
    morceaux = [_trait(centre_a, ya + _BLOC_H, centre_a, coude)]
    if abs(centre_b - centre_a) > 0.5:
        morceaux.append(_trait(centre_a, coude, centre_b, coude))
    morceaux.append(_trait(centre_b, coude, centre_b, yb - _POINTE_H))
    morceaux.append(_pointe(centre_b, yb, "bas"))
    return "".join(morceaux)


def _symbole_terre(x, y):
    """Symbole de terre normalisé : trois traits horizontaux décroissants."""
    return "".join([
        _trait(x, y, x, y + 8),
        _trait(x - 11, y + 8, x + 11, y + 8),
        _trait(x - 7, y + 12, x + 7, y + 12),
        _trait(x - 3, y + 16, x + 3, y + 16),
    ])


# ────────────────────────────────────────────────────────────────── planche
def rendre_schema(entree, resultat, cartouche=None, positions=None):
    """PV39 — rend le schéma unifilaire en SVG (texte), jamais un fichier.

    ``cartouche`` : ``{client, reference, date, indice}`` — aucun montant n'y a
    sa place, c'est un document technique. ``positions`` : surcharge ``{clef:
    {"x": .., "y": ..}}`` par organe.
    """
    blocs = blocs_du_schema(entree, resultat)
    largeur, hauteur = _format_planche(len(blocs))
    places = _positions(blocs, largeur, positions)

    svg = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %s %s" '
        'width="%s" height="%s" font-family="Helvetica, Arial, sans-serif">'
        % (_n(largeur), _n(hauteur), _n(largeur), _n(hauteur)),
        '<rect x="0" y="0" width="%s" height="%s" fill="#ffffff"/>'
        % (_n(largeur), _n(hauteur)),
        '<text x="%s" y="%s" font-size="17" font-weight="700" fill="%s">'
        'Schéma unifilaire — installation photovoltaïque</text>'
        % (_n(_MARGE), _n(_MARGE + 14), _TRAIT),
        '<text x="%s" y="%s" font-size="10" fill="#888888">'
        'Brouillon — dossier technique</text>'
        % (_n(_MARGE), _n(_MARGE + 32)),
    ]

    for place in places:
        svg.append(_bloc_svg(place[1], place[2], place[0]))
    chaine = [place for place in places if not place[4]]
    for depart, arrivee in zip(chaine, chaine[1:]):
        svg.append(_liaison(depart, arrivee))

    svg.append(_branches(places))
    svg.append(_amorces_mppt(entree, resultat, places))
    svg.append(_barrette_de_terre(places))
    svg.append(_tableau(resultat, largeur))
    svg.append(_cartouche(entree, resultat, largeur, hauteur, cartouche))
    svg.append("</svg>")
    return "".join(svg)


def _place(places, clef):
    for place in places:
        if place[0].clef == clef:
            return place
    return None


def _branches(places):
    """Les organes hors chaîne PENDENT sous leur porteur — ici, la batterie.

    La liaison descend depuis le VENTRE de l'onduleur (côté DC) : la branche ne
    coupe pas la chaîne série, elle s'y accroche.

    L'équerre est posée à ``_BRANCHE_EQUERRE_DY`` sous le porteur et la boîte de
    la branche ``_DEGAGEMENT_POINTE`` plus bas (``_BRANCHE_DY`` en dérive) :
    c'est exactement le dégagement que ``_liaison`` s'accorde entre deux
    rangées, et la pointe de 9 px vers la batterie y tient ENTIÈRE.
    """
    ancre = _place(places, _ANCRE_DE_BRANCHE)
    if ancre is None:
        return ""
    morceaux = []
    for place in places:
        if not place[4]:
            continue
        centre = place[1] + _BLOC_L / 2
        depart = ancre[1] + _BLOC_L / 2
        equerre = ancre[2] + _BLOC_H + _BRANCHE_EQUERRE_DY
        morceaux.append(_trait(depart, ancre[2] + _BLOC_H, depart, equerre))
        if abs(centre - depart) > 0.5:
            morceaux.append(_trait(depart, equerre, centre, equerre))
        morceaux.append(
            _trait(centre, equerre, centre, place[2] - _POINTE_H))
        morceaux.append(_pointe(centre, place[2], "bas"))
        # Le libellé se pose SOUS l'équerre, à l'aplomb du conducteur qu'il
        # nomme, et à droite de la descente pour ne pas mordre la pointe. Posé
        # au-dessus (à ``equerre − 5``), il flottait dans la bande de la
        # gouttière de terre POINTILLÉE, qui récupérait la lecture. Le « ⇄ »
        # note que le courant batterie va dans LES DEUX sens (charge et
        # décharge) : une flèche simple, seule, dirait le contraire.
        morceaux.append(
            '<text x="%s" y="%s" font-size="8" fill="%s">'
            'branche DC ⇄</text>'
            % (_n(min(centre, depart) + _POINTE_L + 3.0),
               _n(equerre + _POINTE_H), _TEXTE_SECONDAIRE))
    return "".join(morceaux)


def _plafond_au_dessus(place, places):
    """Le ``y`` le plus BAS qu'une étiquette posée au-dessus de ``place`` peut
    atteindre sans mordre l'organe qui le surplombe.

    On ne regarde QUE les organes dont l'emprise horizontale recoupe celle du
    bloc et qui sont réellement au-dessus de lui : à défaut, le plafond est le
    haut de la zone de dessin (sous le titre et le sous-titre de la planche).
    """
    plafond = (_PLAFOND_DESSIN if place[1] < _LARGEUR_ENTETE
               else _MARGE + 6.0)
    for autre in places:
        if autre is place:
            continue
        bas = autre[2] + _BLOC_H
        if bas > place[2]:
            continue                      # pas au-dessus
        if autre[1] >= place[1] + _BLOC_L or autre[1] + _BLOC_L <= place[1]:
            continue                      # aucune emprise commune
        plafond = max(plafond, bas)
    return plafond


def _halo(x, y, texte, taille=8.0):
    """Fond blanc derrière un texte posé dans une gouttière.

    Les liaisons série descendent par l'aplomb des blocs, donc en plein milieu
    de la gouttière où se posent les étiquettes MPPT. Un fond opaque garde le
    texte lisible sans déplacer la liaison (le trait, lui, reste juste).
    """
    largeur = len(texte) * taille * 0.58 + 6.0
    return ('<rect x="%s" y="%s" width="%s" height="%s" fill="#ffffff"/>'
            % (_n(x - 3), _n(y - taille), _n(largeur), _n(taille + 3.0)))


def _amorces_mppt(entree, resultat, places):
    """Une amorce par entrée MPPT UTILISÉE, étiquetée AU-DESSUS de l'onduleur.

    Les étiquettes étaient posées À GAUCHE des amorces, ancrées « end » : sur
    une rangée parcourue de droite à gauche, l'organe suivant (le disjoncteur
    AC) occupe précisément cette place, et le texte se dessinait PAR-DESSUS sa
    boîte. Ce n'était pas un mauvais réglage mais une impossibilité
    géométrique : l'espace entre deux organes vaut ``_ECART`` (34 px) et une
    étiquette en fait trois fois plus. Elles montent donc dans la gouttière
    au-dessus du bloc, ancrées sur son bord GAUCHE — leur ``x`` est alors, par
    construction, à droite de tout organe qui précède l'onduleur.

    Une entrée SANS chaîne n'est plus dessinée du tout : « MPPT 2 · 0
    chaîne(s) » annonçait une amorce qui n'existe pas dans le câblage (le
    nombre d'entrées de l'appareil, lui, reste lisible sous son titre).
    """
    place = _place(places, "onduleur")
    if place is None:
        return ""
    _bloc, x, y, _rangee = place[:4]
    par_mppt = {}
    for chaine in resultat.chaines:
        par_mppt[chaine.mppt] = par_mppt.get(chaine.mppt, 0) + 1
    entrees = tuple(sorted(rang for rang, nombre in par_mppt.items()
                           if nombre > 0))
    if not entrees:
        return ""

    morceaux = []
    for index, rang in enumerate(entrees):
        yi = y + (_BLOC_H * (index + 1)) / (len(entrees) + 1)
        morceaux.append(_trait(x - 16, yi, x, yi))

    libelles = ["MPPT %d · %d chaîne(s)" % (rang, par_mppt[rang])
                for rang in entrees]
    disponible = y - _ETIQUETTE_DY - _plafond_au_dessus(place, places)
    if len(libelles) * _ETIQUETTE_H > disponible:
        # Trop d'entrées pour la gouttière : une seule ligne, même contenu.
        libelles = ["MPPT · %s chaîne(s)"
                    % "/".join(str(par_mppt[rang]) for rang in entrees)]
    for index, libelle in enumerate(libelles):
        base = (y - _ETIQUETTE_DY
                - (len(libelles) - 1 - index) * _ETIQUETTE_H)
        morceaux.append(_halo(x, base, libelle))
        morceaux.append(
            '<text x="%s" y="%s" font-size="8" fill="%s">%s</text>'
            % (_n(x), _n(base), _TEXTE_SECONDAIRE, _esc(libelle)))
    return "".join(morceaux)


def _barrette_de_terre(places):
    """UNE barrette, à laquelle le champ, l'onduleur et le TGBT sont reliés.

    Le routage compte autant que la liaison : chaque descente part du quart
    GAUCHE du bloc (son centre est l'aplomb de la branche batterie), plonge dans
    la GOUTTIÈRE entre deux rangées, puis rejoint le collecteur vertical le long
    du bord gauche de la planche. Rien ne traverse jamais un organe — sur un
    schéma, un trait qui coupe une boîte se lit comme une liaison à cette boîte.
    """
    ancres = [_place(places, clef) for clef in _A_LA_TERRE]
    ancres = [place for place in ancres if place is not None]
    if not ancres:
        return ""
    # La barrette passe SOUS tout le dessin, branches comprises.
    barre_y = max(place[2] for place in places) + _BLOC_H + 44.0
    collecteur_x = _MARGE - 14.0
    morceaux = []
    for place in ancres:
        depart = place[1] + _BLOC_L * 0.15
        gouttiere = place[2] + _BLOC_H + _GOUTTIERE_DY
        morceaux.append(_trait(depart, place[2] + _BLOC_H, depart, gouttiere,
                               pointille=True))
        morceaux.append(_trait(depart, gouttiere, collecteur_x, gouttiere,
                               pointille=True))
    haut = min(place[2] for place in ancres) + _BLOC_H + _GOUTTIERE_DY
    morceaux.append(_trait(collecteur_x, haut, collecteur_x, barre_y))
    morceaux.append(_trait(collecteur_x, barre_y, collecteur_x + 60, barre_y))
    morceaux.append(_symbole_terre(collecteur_x + 60, barre_y))
    morceaux.append(
        '<text x="%s" y="%s" font-size="9" fill="%s">Barrette de terre '
        'unique — liaison équipotentielle des masses (T1 / T2)</text>'
        % (_n(collecteur_x + 76), _n(barre_y - 6), _TEXTE_SECONDAIRE))
    return "".join(morceaux)


def _tableau(resultat, largeur):
    """Tableau d'équipements, à droite — même source que le bordereau."""
    lignes = lignes_tableau(resultat)
    x = largeur - _MARGE - _TABLEAU_L
    y = _MARGE + 54.0
    hauteur_ligne = 17.0
    morceaux = [
        '<rect x="%s" y="%s" width="%s" height="%s" fill="#ffffff" '
        'stroke="%s" stroke-width="1.5"/>'
        % (_n(x), _n(y), _n(_TABLEAU_L),
           _n(hauteur_ligne * (len(lignes) + 2) + 8), _TRAIT),
        '<text x="%s" y="%s" font-size="11" font-weight="700" fill="%s">'
        'Nomenclature des équipements</text>'
        % (_n(x + 8), _n(y + 16), _TRAIT),
    ]
    entetes = ("Repère", "Désignation", "Calibre / section", "Qté")
    colonnes = (x + 8, x + 58, x + 214, x + 296)
    ligne_y = y + 16 + hauteur_ligne
    for index, entete in enumerate(entetes):
        morceaux.append(
            '<text x="%s" y="%s" font-size="8" font-weight="700" fill="%s">'
            '%s</text>' % (_n(colonnes[index]), _n(ligne_y), _TRAIT,
                           _esc(entete)))
    for ligne in lignes:
        ligne_y += hauteur_ligne
        for index, valeur in enumerate(ligne):
            morceaux.append(
                '<text x="%s" y="%s" font-size="8" fill="%s">%s</text>'
                % (_n(colonnes[index]), _n(ligne_y), _TEXTE_SECONDAIRE,
                   _esc(_tronquer(valeur, 34 if index == 1 else 20))))
    return "".join(morceaux)


def _tronquer(texte, taille):
    texte = str(texte)
    return texte if len(texte) <= taille else texte[:taille - 1] + "…"


def _cartouche(entree, resultat, largeur, hauteur, cartouche):
    """Cartouche technique — client, référence, puissance, date, indice.

    Aucun montant : ce document part au bureau de contrôle et au gestionnaire de
    réseau, pas au client comme offre commerciale.
    """
    donnees = dict(cartouche or {})
    x = largeur - _MARGE - _TABLEAU_L
    lignes = [
        ("Client", donnees.get("client", "—")),
        ("Référence", donnees.get("reference", "—")),
        ("Puissance crête", "%s kWc" % fr(entree.puissance_kwc, 2)),
    ]
    # Le matériel RÉEL, quand le dossier le connaît : un cartouche qui dit
    # « Puissance crête 9,94 kWc » sans dire AVEC QUOI oblige le lecteur à
    # remonter au devis. Rien n'est écrit tant que rien n'est su.
    if entree.module.designation:
        lignes.append(("Modules", entree.module.designation))
    if entree.onduleur.designation:
        lignes.append(("Onduleur", entree.onduleur.designation))
    if entree.batterie and entree.batterie_designation:
        lignes.append(("Stockage", entree.batterie_designation))
    lignes.extend([
        ("Régime / phases", "%s · %s" % (
            entree.regime,
            "triphasé" if int(entree.phases or 1) == 3 else "monophasé")),
        ("Date", donnees.get("date", "—")),
        ("Indice", donnees.get("indice", "A")),
        ("Moteur", "v%s" % resultat.version_moteur),
    ])
    hauteur_cartouche = 14.0 + 13.0 * len(lignes) + 8.0
    y = hauteur - _MARGE - hauteur_cartouche
    morceaux = [
        '<rect x="%s" y="%s" width="%s" height="%s" fill="#ffffff" '
        'stroke="%s" stroke-width="1.5"/>'
        % (_n(x), _n(y), _n(_TABLEAU_L), _n(hauteur_cartouche), _TRAIT),
        '<text x="%s" y="%s" font-size="9" font-weight="700" fill="#888888">'
        'Brouillon — dossier technique</text>' % (_n(x + 8), _n(y + 14)),
    ]
    ligne_y = y + 14
    for intitule, valeur in lignes:
        ligne_y += 13
        morceaux.append(
            '<text x="%s" y="%s" font-size="8" fill="%s">%s</text>'
            % (_n(x + 8), _n(ligne_y), _TEXTE_SECONDAIRE, _esc(intitule)))
        morceaux.append(
            '<text x="%s" y="%s" font-size="8" font-weight="600" fill="%s">'
            '%s</text>' % (_n(x + 118), _n(ligne_y), _TRAIT,
                           _esc(_tronquer(valeur, 30))))
    return "".join(morceaux)
