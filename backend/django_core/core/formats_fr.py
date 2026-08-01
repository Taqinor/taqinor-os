# -*- coding: utf-8 -*-
"""AOF110 — `core.formats_fr` : UN SEUL formateur français pour les TROIS canaux.

Un dossier d'appel d'offres sort par trois tuyaux différents — le mémoire
HTML/PDF (WeasyPrint), le bordereau XLSX (openpyxl) et les cartouches de
planche (matplotlib). Trois tuyaux = trois formateurs improvisés = **trois
rendus différents du même montant dans le même dossier** (« 4 999 920,00 DH »,
« 4999920.0 DH », « 4 999 920 Dh »). C'est la classe de défaut que tout le
groupe AOF combat, appliquée à la typographie : ce module est le formateur
UNIQUE, et le test d'égalité tri-canal en fait une propriété prouvée.

Conventions appliquées (typographie française, Imprimerie nationale)
--------------------------------------------------------------------
* **Groupement des milliers** : espace insécable FINE ``U+202F`` — avec repli
  automatique sur l'espace insécable pleine ``U+00A0`` si une police du dossier
  ne porte PAS le glyphe fin (le piège classique : le lecteur reçoit un carré
  « tofu » au milieu d'un montant, sur un document contractuel).
* **Séparateur décimal** : la virgule.
* **Unité** : séparée du nombre par une espace insécable PLEINE ``U+00A0``,
  toujours — la fine est réservée au groupement. Le symbole ``%`` suit la même
  règle (« 12,5 % »). Unités du dossier : DH, MAD, kWc, kWh, m³/h, m³, m, %.
* **Dates** : ``jj/mm/aaaa``.
* **Négatif** : le signe ASCII ``-`` (le moins typographique U+2212 est un
  second piège de couverture de police — on ne l'introduit pas).

La résolution fine/pleine est prise UNE FOIS pour tout le dossier
--------------------------------------------------------------------
``espace_groupement()`` interroge la couverture de police de TOUS les canaux et
ne garde la fine que si AUCUN canal n'est prouvé dépourvu du glyphe. Deux
conséquences voulues :

1. le paramètre ``canal`` des formateurs ne peut PAS faire diverger la chaîne
   produite (c'est le plus petit dénominateur commun qui gagne, pas le canal
   courant) — il reste accepté pour l'intention d'appel et le diagnostic ;
2. une couverture INCONNUE (police non sondable, bibliothèque absente) ne
   déclenche pas le repli : seul un glyphe prouvé manquant le déclenche.

NOTE XLSX (le piège du canal tableur) : écrire la CHAÎNE produite ici
(``cellule.value = formater_montant(...)``, ``cellule.number_format =
FORMAT_TEXTE_XLSX``). Ne JAMAIS confier la mise en forme à un code Excel du
type ``#,##0.00`` : ses séparateurs sont des ESPACES RÉSERVÉS réinterprétés
selon la locale du lecteur — le même fichier afficherait « 1,234.56 » chez un
lecteur anglophone, c'est-à-dire exactement la divergence que ce module
supprime.

Fondation pure : au niveau module ce fichier n'importe QUE la stdlib. Les
bibliothèques lourdes (fontTools, matplotlib) et ``fc-match`` ne sont touchés
qu'à l'intérieur des sondes de couverture, en import paresseux et sous
``try``. ``weasyprint`` n'est JAMAIS importé (garde ARC11 : tout rendu PDF
passe par ``core.pdf.render_pdf``) — le canal HTML est sondé par son résolveur
de polices, pas par le moteur de rendu.
"""
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

__all__ = [
    'ESPACE_FINE', 'ESPACE_INSECABLE', 'SEPARATEUR_DECIMAL',
    'CODEPOINT_ESPACE_FINE', 'FORMAT_TEXTE_XLSX',
    'CANAL_HTML', 'CANAL_XLSX', 'CANAL_MATPLOTLIB', 'CANAUX',
    'UNITES', 'DECIMALES_PAR_UNITE', 'normaliser_unite',
    'police_couvre_codepoint', 'polices_du_canal', 'couverture_fine',
    'espace_groupement', 'definir_espace_groupement', 'reinitialiser_polices',
    'diagnostic_polices',
    'formater_nombre', 'formater_montant', 'formater_quantite',
    'formater_pourcentage', 'formater_date',
]

# ── Constantes typographiques ────────────────────────────────────────────────

#: U+202F NARROW NO-BREAK SPACE — le groupement des milliers en français.
ESPACE_FINE = ' '
#: U+00A0 NO-BREAK SPACE — le repli universel, et l'espace avant l'unité.
#: Ces deux constantes sont des caractères INVISIBLES dans le source : un
#: éditeur qui «nettoie les espaces» peut les détruire sans que rien ne se voie
#: — un test verrouille donc leur point de code (voir test_formats_fr).
ESPACE_INSECABLE = ' '
CODEPOINT_ESPACE_FINE = 0x202F
SEPARATEUR_DECIMAL = ','
#: Code de format Excel « Texte » : empêche le tableur de re-parser la chaîne.
FORMAT_TEXTE_XLSX = '@'

CANAL_HTML = 'html'
CANAL_XLSX = 'xlsx'
CANAL_MATPLOTLIB = 'matplotlib'
#: Les trois canaux du dossier, dans l'ordre de la chaîne documentaire.
CANAUX = (CANAL_HTML, CANAL_XLSX, CANAL_MATPLOTLIB)

# Familles sondées pour le canal HTML/PDF : celles réellement installées dans
# l'image de production (Dockerfile : fonts-liberation, fonts-noto-core). Une
# CSS qui demande « Arial, Helvetica, sans-serif » est résolue vers l'une
# d'elles par fontconfig — c'est donc leur couverture qui décide.
FAMILLES_HTML = ('Liberation Sans', 'Noto Sans', 'DejaVu Sans')
# Le canal XLSX est rendu par le TABLEUR du lecteur, avec SA police : elle
# n'est pas sondable ici (couverture « inconnue », jamais « absente »).
FAMILLES_XLSX = ()

# ── Unités du dossier ────────────────────────────────────────────────────────

#: Formes canoniques acceptées (la valeur est ce qui sera imprimé).
UNITES = ('DH', 'MAD', 'kWc', 'kW', 'kWh', 'MWh', 'm³/h', 'm³', 'm', '%')

#: Nombre de décimales par défaut, par unité (surchargeable à l'appel).
DECIMALES_PAR_UNITE = {
    'DH': 2, 'MAD': 2,
    'kWc': 2, 'kW': 2, 'kWh': 0, 'MWh': 2,
    'm³/h': 1, 'm³': 1, 'm': 2,
    '%': 1,
}
DECIMALES_PAR_DEFAUT = 2

_ALIAS_UNITES = {
    'dh': 'DH', 'dhs': 'DH', 'dirham': 'DH', 'dirhams': 'DH',
    'mad': 'MAD',
    'kwc': 'kWc', 'kwp': 'kWc', 'kw': 'kW', 'kwh': 'kWh', 'mwh': 'MWh',
    'm3/h': 'm³/h', 'm³/h': 'm³/h', 'm3h': 'm³/h',
    'm3': 'm³', 'm³': 'm³', 'm': 'm',
    '%': '%', 'pourcent': '%',
}


def normaliser_unite(unite):
    """'kwc' → 'kWc', 'm3/h' → 'm³/h'. Une unité inconnue est rendue telle
    quelle (nettoyée) : le formateur n'a pas à connaître tout le SI."""
    if unite is None:
        return ''
    brut = str(unite).strip()
    return _ALIAS_UNITES.get(brut.lower(), brut)


# ── Sonde de couverture de police (le glyphe fin manquant) ───────────────────

_CACHE_COUVERTURE = {}
_CACHE_POLICES = {}
_CACHE_ESPACE = {}
_ESPACE_FORCE = None


def police_couvre_codepoint(chemin, codepoint=CODEPOINT_ESPACE_FINE):
    """La police de ``chemin`` porte-t-elle ``codepoint`` ?

    Retourne ``True``/``False``, ou ``None`` quand la question ne peut pas être
    tranchée (fontTools absent, fichier illisible) — « inconnu » n'est PAS
    « absent » : seule une absence PROUVÉE déclenche le repli.
    """
    try:
        from fontTools.ttLib import TTFont
    except Exception:
        return None
    police = None
    try:
        police = TTFont(chemin, fontNumber=0, lazy=True)
        return codepoint in police.getBestCmap()
    except Exception:
        return None
    finally:
        if police is not None:
            try:
                police.close()
            except Exception:
                pass


def _polices_fontconfig(familles):
    """Résolution par fontconfig — le résolveur RÉEL de Pango/WeasyPrint."""
    try:
        import shutil
        import subprocess
    except Exception:
        return []
    binaire = shutil.which('fc-match')
    if not binaire:
        return []
    chemins = []
    for famille in familles:
        try:
            issue = subprocess.run(
                [binaire, '-f', '%{file}', str(famille)],
                capture_output=True, text=True, timeout=5)
        except Exception:
            continue
        chemin = (issue.stdout or '').strip()
        if chemin and chemin not in chemins:
            chemins.append(chemin)
    return chemins


def _polices_matplotlib(familles=None, repli=True):
    """Résolution par l'index de polices de matplotlib.

    ``repli=False`` interdit le rabattement silencieux sur DejaVu Sans : pour
    le canal HTML, prétendre que la famille demandée est couverte parce que la
    police de SECOURS de matplotlib l'est serait un faux négatif (le dossier
    partirait avec un carré tofu). Le canal matplotlib, lui, utilisera bel et
    bien ce rabattement : il est donc autorisé là-bas.
    """
    try:
        from matplotlib import rcParams
        from matplotlib.font_manager import FontProperties, findfont
    except Exception:
        return []
    if familles is None:
        familles = rcParams.get('font.family') or ['sans-serif']
    if isinstance(familles, str):
        familles = [familles]
    chemins = []
    for famille in familles:
        try:
            chemin = findfont(FontProperties(family=[str(famille)]),
                              fallback_to_default=repli)
        except Exception:
            continue
        if chemin and chemin not in chemins:
            chemins.append(chemin)
    return chemins


def polices_du_canal(canal, familles=None):
    """Fichiers de police que ``canal`` utilisera réellement (liste, possiblement
    vide quand rien n'est sondable)."""
    _valider_canal(canal)
    cle = (canal, tuple(familles) if familles is not None else None)
    if cle in _CACHE_POLICES:
        return list(_CACHE_POLICES[cle])
    if canal == CANAL_MATPLOTLIB:
        chemins = _polices_matplotlib(familles, repli=True)
    elif canal == CANAL_XLSX:
        chemins = []
        if familles or FAMILLES_XLSX:
            demandees = familles if familles is not None else FAMILLES_XLSX
            chemins = (_polices_fontconfig(demandees)
                       or _polices_matplotlib(demandees, repli=False))
    else:  # CANAL_HTML — WeasyPrint passe par Pango/fontconfig.
        demandees = familles if familles is not None else FAMILLES_HTML
        chemins = (_polices_fontconfig(demandees)
                   # À défaut du binaire fontconfig, on interroge le MÊME parc
                   # de polices système via l'index matplotlib : ce sont les
                   # mêmes fichiers, sans rabattement toléré.
                   or _polices_matplotlib(demandees, repli=False))
    _CACHE_POLICES[cle] = list(chemins)
    return list(chemins)


def couverture_fine(canal, familles=None):
    """``True`` si le canal porte U+202F, ``False`` si une de ses polices en est
    PROUVÉE dépourvue, ``None`` si la question reste ouverte."""
    _valider_canal(canal)
    cle = (canal, tuple(familles) if familles is not None else None)
    if cle in _CACHE_COUVERTURE:
        return _CACHE_COUVERTURE[cle]
    resultats = [police_couvre_codepoint(chemin)
                 for chemin in polices_du_canal(canal, familles)]
    if any(resultat is False for resultat in resultats):
        verdict = False
    elif any(resultat is True for resultat in resultats):
        verdict = True
    else:
        verdict = None
    _CACHE_COUVERTURE[cle] = verdict
    return verdict


def espace_groupement(canaux=CANAUX):
    """L'espace de groupement du DOSSIER : fine si tous les canaux la portent.

    Un seul canal prouvé dépourvu du glyphe fait basculer TOUT le dossier sur
    l'espace insécable pleine — c'est ce qui garantit que les trois canaux
    impriment la même chaîne (test d'égalité tri-canal).
    """
    if _ESPACE_FORCE is not None:
        return _ESPACE_FORCE
    cle = tuple(canaux)
    if cle in _CACHE_ESPACE:
        return _CACHE_ESPACE[cle]
    couvertures = [couverture_fine(canal) for canal in cle]
    espace = (ESPACE_INSECABLE if any(c is False for c in couvertures)
              else ESPACE_FINE)
    _CACHE_ESPACE[cle] = espace
    return espace


def definir_espace_groupement(espace):
    """Force l'espace de groupement (décision fondateur / rendu de référence).

    ``None`` rend la main à la détection automatique.
    """
    global _ESPACE_FORCE
    if espace is not None and espace not in (ESPACE_FINE, ESPACE_INSECABLE):
        raise ValueError(
            'espace de groupement invalide : attendus U+202F (fine) ou '
            'U+00A0 (insécable pleine)')
    _ESPACE_FORCE = espace


def reinitialiser_polices():
    """Vide les caches de sonde (tests, ou après installation de polices)."""
    _CACHE_COUVERTURE.clear()
    _CACHE_POLICES.clear()
    _CACHE_ESPACE.clear()


def diagnostic_polices(canaux=CANAUX):
    """Rapport lisible : par canal, les fichiers sondés et le verdict."""
    return {
        canal: {
            'polices': polices_du_canal(canal),
            'couverture_fine': couverture_fine(canal),
        }
        for canal in canaux
    }


# ── Formateurs ───────────────────────────────────────────────────────────────

def _valider_canal(canal):
    if canal not in CANAUX:
        raise ValueError(
            f'canal inconnu : {canal!r} (attendus : {", ".join(CANAUX)})')
    return canal


def _quantifier(valeur, decimales):
    """Decimal arrondi à ``decimales``, moitié-vers-le-haut.

    Même politique que ``core.money.quantize_mad`` (ROUND_HALF_UP), généralisée
    à un nombre quelconque de décimales — un rendu ne doit jamais arrondir
    autrement que la comptabilité qui l'alimente.
    """
    if isinstance(valeur, Decimal):
        nombre = valeur
    else:
        nombre = Decimal(str(valeur))
    return nombre.quantize(Decimal(1).scaleb(-int(decimales)),
                           rounding=ROUND_HALF_UP)


def _grouper(entier, espace):
    morceaux = []
    while len(entier) > 3:
        morceaux.insert(0, entier[-3:])
        entier = entier[:-3]
    morceaux.insert(0, entier)
    return espace.join(morceaux)


def formater_nombre(valeur, decimales=DECIMALES_PAR_DEFAUT, canal=CANAL_HTML,
                    espace=None, grouper=True):
    """Nombre → chaîne française (« 4 999 920,00 », espaces fines insécables).

    :param decimales: nombre de décimales (arrondi moitié-vers-le-haut).
    :param canal: ``CANAL_HTML`` / ``CANAL_XLSX`` / ``CANAL_MATPLOTLIB``. Il ne
        peut pas faire diverger la chaîne (voir l'en-tête du module) ; il est
        validé pour attraper une faute de frappe d'appelant.
    :param espace: force l'espace de groupement (rendu de référence / test
        doré) ; ``None`` = résolution automatique pour tout le dossier.
    :param grouper: ``False`` supprime le groupement (numéros, années).
    """
    _valider_canal(canal)
    decimales = max(0, int(decimales))
    nombre = _quantifier(valeur, decimales)
    negatif = nombre < 0
    texte = f'{abs(nombre):.{decimales}f}'
    entier, _, fraction = texte.partition('.')
    if grouper:
        entier = _grouper(entier, espace if espace is not None
                          else espace_groupement())
    rendu = entier + (SEPARATEUR_DECIMAL + fraction if fraction else '')
    return ('-' + rendu) if negatif else rendu


def formater_quantite(valeur, unite, decimales=None, canal=CANAL_HTML,
                      espace=None, grouper=True):
    """Nombre + unité, séparés par une espace insécable pleine.

    « 4 999 920,00 DH », « 12,50 kWc », « 45,0 m³/h », « 12,5 % ».
    ``decimales=None`` prend la valeur par défaut de l'unité.
    """
    canonique = normaliser_unite(unite)
    if decimales is None:
        decimales = DECIMALES_PAR_UNITE.get(canonique, DECIMALES_PAR_DEFAUT)
    nombre = formater_nombre(valeur, decimales=decimales, canal=canal,
                             espace=espace, grouper=grouper)
    if not canonique:
        return nombre
    return nombre + ESPACE_INSECABLE + canonique


def formater_montant(valeur, devise='DH', decimales=2, canal=CANAL_HTML,
                     espace=None):
    """Montant → « 4 999 920,00 DH » (le rendu contractuel du dossier)."""
    return formater_quantite(valeur, devise, decimales=decimales, canal=canal,
                             espace=espace)


def formater_pourcentage(valeur, decimales=1, canal=CANAL_HTML, espace=None):
    """Pourcentage → « 12,5 % » (la valeur est DÉJÀ en pourcentage)."""
    return formater_quantite(valeur, '%', decimales=decimales, canal=canal,
                             espace=espace)


def formater_date(valeur, canal=CANAL_HTML):
    """Date → ``jj/mm/aaaa``. Accepte ``date``/``datetime``/ISO/``None``."""
    _valider_canal(canal)
    if valeur is None or valeur == '':
        return ''
    if isinstance(valeur, datetime):
        jour = valeur.date()
    elif isinstance(valeur, date):
        jour = valeur
    else:
        texte = str(valeur).strip()
        try:
            jour = datetime.fromisoformat(texte.replace('Z', '+00:00'))
        except ValueError:
            raise ValueError(f'date illisible : {valeur!r} (attendu : objet '
                             f'date/datetime ou chaîne ISO aaaa-mm-jj)')
        if isinstance(jour, datetime):
            jour = jour.date()
    return f'{jour.day:02d}/{jour.month:02d}/{jour.year:04d}'
