#!/usr/bin/env python3
"""Génère le guide PDF « Le suivi commercial : étapes, réponses et suites ».

ORDRE FONDATEUR (30/09/2026) : « show a new pdf document that you upload
directly to my documentation module showing how those steps work and to what
every answer leads to ».

SOURCE UNIQUE. Le guide est GÉNÉRÉ depuis la table du parcours
(``frontend/src/features/crm/relances/parcours_suivi.json``) : aucune question,
aucune réponse, aucun « ce qui se passe ensuite » n'est retapé ici. Les délais
des protocoles (prise de contact, suivi de proposition, réveils) se lisent dans
``backend/django_core/apps/parametres/models_relance.py`` : ce module ne peut
pas être importé sans Django, le script le PARSE avec ``ast`` (aucune exécution)
et n'en recopie rien. Seuls quelques textes de liaison (règles, boutons de la
fiche du lead, « ce qui a changé ») sont écrits ici, en français simple.

CE QUE FAIT UN LANCEMENT (bibliothèque standard seulement, rien n'est demandé au
clavier, relançable à volonté) :
  1. écrit ``docs/meryem/source/suivi_commercial_etapes_et_reponses.html``
     (UTF-8, fins de ligne LF) — sa balise ``table-sha256`` est l'empreinte de
     la table lue en texte normalisé (``\\r\\n`` -> ``\\n``) : c'est elle que la
     garde ``apps/ged/tests_guide_suivi_a_jour.py`` compare ;
  2. met à jour l'entrée du guide dans ``docs/meryem/manifest.json`` (la
     ``version`` est celle de la table) ;
  3. imprime le PDF ``docs/meryem/Suivi_commercial_etapes_et_reponses.pdf`` avec
     Edge sans tête — seulement si le HTML a changé ou si le PDF manque, pour ne
     pas fabriquer une « nouvelle version » GED à chaque lancement (un PDF Edge
     n'est jamais identique octet pour octet : il porte sa date de création).

Usage :
    python scripts/generer_guide_suivi.py                    # HTML + manifeste + PDF
    python scripts/generer_guide_suivi.py --html-seulement   # machine sans Edge
    python scripts/generer_guide_suivi.py --forcer           # réimprime le PDF
    python scripts/generer_guide_suivi.py --visite           # + guide de la visite
    python scripts/generer_guide_suivi.py --edge "C:\\...\\msedge.exe"

``--visite`` réimprime aussi le guide de la visite technique : sa source HTML est
la fixture ``apps/ged/fixtures/guide_visite_suivi_commercial.html`` ; le PDF est
écrit à DEUX endroits, octet pour octet identiques (``docs/meryem/`` pour la
publication, et la fixture que lit ``seed_guide_visite``).

IMPRESSION. La commande d'Edge est
``msedge --headless=new --disable-gpu --no-pdf-header-footer
--user-data-dir=<dossier temporaire UNIQUE> --no-first-run --print-to-pdf=<pdf>
file:///<html>``. Le ``--user-data-dir`` unique est OBLIGATOIRE : sans lui, un
Edge déjà ouvert avale la commande et n'écrit rien. Les rendus sont séquentiels
(jamais deux en parallèle).

Codes de sortie : 0 = tout est fait ; 1 = l'impression a échoué ; 2 = problème
de fichier, de table ou d'Edge (message en français).
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
from pathlib import Path
from types import SimpleNamespace

RACINE = Path(__file__).resolve().parent.parent

# Destination GED de ce guide (dossier RACINE du cabinet) : la même que le guide
# de la visite, déposé par ``seed_guide_visite`` (services.GUIDE_VISITE_*).
FICHIER_PDF = 'Suivi_commercial_etapes_et_reponses.pdf'
TITRE_GED = 'Guide — Le suivi commercial : étapes, réponses et suites'
DESCRIPTION_GED = (
    'Pour chaque étape du suivi commercial : la question posée, les réponses '
    'possibles et ce que chaque réponse déclenche ensuite, du premier appel à '
    'la signature.')
CABINET_GED = 'Documentation'
DOSSIER_GED = 'Guides'

DATE_CHANGEMENTS = '30/09/2026'

EDGE_CANDIDATS = (
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
)
DELAI_IMPRESSION = 180  # secondes
TAILLE_PDF_MINI = 10_000  # octets : en dessous, l'impression est ratée


def chemins(racine: Path = RACINE) -> SimpleNamespace:
    """Tous les chemins du script, dérivés de la racine du dépôt."""
    docs = racine / 'docs' / 'meryem'
    visite_html = (racine / 'backend' / 'django_core' / 'apps' / 'ged'
                   / 'fixtures' / 'guide_visite_suivi_commercial.html')
    return SimpleNamespace(
        table=racine / 'frontend' / 'src' / 'features' / 'crm' / 'relances'
        / 'parcours_suivi.json',
        gabarits=racine / 'backend' / 'django_core' / 'apps' / 'parametres'
        / 'models_relance.py',
        html=docs / 'source' / 'suivi_commercial_etapes_et_reponses.html',
        pdf=docs / FICHIER_PDF,
        manifeste=docs / 'manifest.json',
        visite_html=visite_html,
        visite_pdf_docs=docs / 'Guide_visite_suivi_commercial.pdf',
        visite_pdf_fixture=visite_html.with_suffix('.pdf'),
    )


def erreur(message: str, code: int = 2):
    print(message, file=sys.stderr)
    raise SystemExit(code)


def normaliser_lf(texte: str) -> str:
    return texte.replace('\r\n', '\n')


def date_fr(iso: str) -> str:
    """``2026-09-30`` -> ``30/09/2026``."""
    m = re.fullmatch(r'(\d{4})-(\d{2})-(\d{2})', iso or '')
    if not m:
        erreur(f'La date « maj » de la table est illisible : {iso!r} (AAAA-MM-JJ attendu).')
    return f'{m.group(3)}/{m.group(2)}/{m.group(1)}'


def liste_fr(elements) -> str:
    elements = list(elements)
    if len(elements) <= 1:
        return ''.join(elements)
    return ', '.join(elements[:-1]) + ' et ' + elements[-1]


def pluriel(n: int, singulier: str, pluriel_: str) -> str:
    return f'{n} {singulier if n <= 1 else pluriel_}'


# ══════════════════════════════════════════════════════════════════════════════
# 1. LECTURE DE LA TABLE ET DES GABARITS
# ══════════════════════════════════════════════════════════════════════════════

def lire_table(chemin: Path):
    """``(table, empreinte)`` — l'empreinte est celle du texte normalisé LF."""
    try:
        brut = chemin.read_bytes().decode('utf-8')
    except OSError as exc:
        erreur(f'Table du parcours introuvable ({chemin}) : {exc}')
    texte = normaliser_lf(brut)
    try:
        table = json.loads(texte)
    except ValueError as exc:
        erreur(f'Table du parcours illisible ({chemin}) : {exc}')
    empreinte = hashlib.sha256(texte.encode('utf-8')).hexdigest()
    for cle in ('version', 'maj', 'modeles', 'gestes', 'etapes', 'evenements'):
        if cle not in table:
            erreur(f'La table du parcours ne contient pas « {cle} ».')
    return table, empreinte


class _NonEvaluable(Exception):
    pass


def _evaluer(noeud, env, classes):
    """Évalue un littéral du module des gabarits (sans rien exécuter).

    Gère les constantes, les listes/dictionnaires/tuples, les noms déjà définis
    plus haut, ``Classe.MEMBRE`` d'un ``TextChoices`` (sa valeur) et
    ``datetime.time(h, m)`` (rendu ``HH:MM``)."""
    if isinstance(noeud, ast.Constant):
        return noeud.value
    if isinstance(noeud, ast.Name):
        if noeud.id in env:
            return env[noeud.id]
        raise _NonEvaluable(noeud.id)
    if isinstance(noeud, ast.Attribute) and isinstance(noeud.value, ast.Name):
        membres = classes.get(noeud.value.id)
        if membres and noeud.attr in membres:
            return membres[noeud.attr][0]
        raise _NonEvaluable(f'{noeud.value.id}.{noeud.attr}')
    if isinstance(noeud, ast.List):
        return [_evaluer(e, env, classes) for e in noeud.elts]
    if isinstance(noeud, ast.Tuple):
        return tuple(_evaluer(e, env, classes) for e in noeud.elts)
    if isinstance(noeud, ast.Dict):
        if any(k is None for k in noeud.keys):
            raise _NonEvaluable('**')
        return {_evaluer(k, env, classes): _evaluer(v, env, classes)
                for k, v in zip(noeud.keys, noeud.values)}
    if (isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Attribute)
            and noeud.func.attr == 'time' and not noeud.keywords):
        args = [_evaluer(a, env, classes) for a in noeud.args]
        return '{:02d}:{:02d}'.format(*(list(args) + [0, 0])[:2])
    raise _NonEvaluable(type(noeud).__name__)


def lire_gabarits(chemin: Path) -> dict:
    """Les trois protocoles et les libellés de canaux, lus par ``ast``."""
    try:
        source = chemin.read_text(encoding='utf-8')
    except OSError as exc:
        erreur(f'Gabarits de relance introuvables ({chemin}) : {exc}')
    arbre = ast.parse(source)
    classes: dict = {}
    env: dict = {}
    for noeud in arbre.body:
        if isinstance(noeud, ast.ClassDef):
            membres = {}
            for instr in noeud.body:
                if (isinstance(instr, ast.Assign) and len(instr.targets) == 1
                        and isinstance(instr.targets[0], ast.Name)
                        and isinstance(instr.value, ast.Tuple)
                        and len(instr.value.elts) == 2
                        and all(isinstance(e, ast.Constant) and isinstance(e.value, str)
                                for e in instr.value.elts)):
                    membres[instr.targets[0].id] = (
                        instr.value.elts[0].value, instr.value.elts[1].value)
            classes[noeud.name] = membres
        elif (isinstance(noeud, ast.Assign) and len(noeud.targets) == 1
              and isinstance(noeud.targets[0], ast.Name)):
            try:
                env[noeud.targets[0].id] = _evaluer(noeud.value, env, classes)
            except _NonEvaluable:
                continue
    noms = {
        'contact': 'CADENCE_CONTACT_DEFAUT',
        'apres_devis': 'CADENCE_APRES_DEVIS_DEFAUT',
        'reveil': 'CADENCE_REVEIL_DEFAUT',
    }
    protocoles = {}
    for cle, nom in noms.items():
        touches = env.get(nom)
        if not isinstance(touches, list) or not touches:
            erreur(f'{chemin.name} : {nom} est introuvable ou illisible.')
        for t in touches:
            for champ in ('ordre', 'delai_jours', 'canal', 'libelle'):
                if champ not in t:
                    erreur(f'{chemin.name} : {nom} : une touche n\u2019a pas « {champ} ».')
        protocoles[cle] = sorted(touches, key=lambda t: t['ordre'])
    canaux = {valeur: libelle for valeur, libelle in classes.get('CanalRelance', {}).values()}
    if not canaux:
        erreur(f'{chemin.name} : la liste des canaux (CanalRelance) est introuvable.')
    return {'protocoles': protocoles, 'canaux': canaux}


def jour_lisible(touche: dict) -> str:
    """``J0``, ``J0 + 3 min``, ``J0 + 2 h 30``, ``J14``…"""
    jours = int(touche.get('delai_jours') or 0)
    minutes = int(touche.get('delai_minutes') or 0)
    base = f'J{jours}'
    if not minutes:
        return base
    heures, reste = divmod(minutes, 60)
    if heures and reste:
        return f'{base} + {heures} h {reste:02d}'
    if heures:
        return f'{base} + {heures} h'
    return f'{base} + {reste} min'


def reponses_resolues(table: dict, etape: dict) -> list:
    """Les réponses d'une étape : ``{**modeles[r.modele], **r}``."""
    out = []
    for r in etape['reponses']:
        modele = table['modeles'].get(r.get('modele'))
        if modele is None:
            erreur(f'Table : l\u2019étape « {etape["id"]} » cite un modèle de réponse '
                   f'inconnu : {r.get("modele")!r}.')
        fusion = {**modele, **r}
        if not fusion.get('label') or not fusion.get('effet'):
            erreur(f'Table : la réponse « {r.get("modele")} » de l\u2019étape '
                   f'« {etape["id"]} » n\u2019a pas de libellé ou pas d\u2019effet.')
        out.append(fusion)
    return out


def valider_table(table: dict) -> None:
    """Refuse (message en français) une table dont il manquerait un champ que
    le guide affiche — plutôt qu'un guide troué ou une trace Python."""
    for etape in table['etapes']:
        for cle in ('id', 'famille', 'nom', 'question', 'reponses'):
            if not etape.get(cle):
                erreur(f'Table : l’étape « {etape.get("id", "?")} » n’a pas de champ « {cle} ».')
    for section, champs in (('gestes', ('label', 'effet')), ('evenements', ('quand', 'effet'))):
        for element in table[section]:
            for cle in champs:
                if not element.get(cle):
                    erreur(f'Table : un élément de « {section} » n’a pas de champ « {cle} » '
                           f'({element.get("id", "?")}).')


def exiger_etapes(table: dict, ids) -> None:
    """Le schéma s'appuie sur ces étapes : si la table en retire une, on le dit."""
    presentes = {e['id'] for e in table['etapes']}
    manquantes = [i for i in ids if i not in presentes]
    if manquantes:
        erreur('Le schéma du parcours s\u2019appuie sur des étapes absentes de la table : '
               + ', '.join(manquantes))


# ══════════════════════════════════════════════════════════════════════════════
# 2. TYPOGRAPHIE ET LANGAGE
# ══════════════════════════════════════════════════════════════════════════════

# Adaptations de langage : la table est écrite par des développeurs, ce guide
# est lu par des commerciaux. Ces remplacements de PHRASES exactes (jamais du
# texte inventé) ramènent au français courant les rares termes techniques ou le
# vouvoiement de la table. Elles ne touchent ni les questions ni les libellés
# de réponse (ce sont les mots de l'écran, cités tels quels). Une adaptation qui
# ne correspond plus à rien (la table a été reformulée à la source) est
# simplement ignorée.
ADAPTATIONS = (
    ('Sur une étape posée par le moteur', 'Sur une étape posée par l\u2019ERP'),
    ('Une cadence de reprise est posée.', 'Un suivi de reprise est posé.'),
    ('Vous avez appelé au lieu d\u2019écrire', 'Tu as appelé au lieu d\u2019écrire'),
    ('Vous l\u2019avez eu au téléphone', 'Tu l\u2019as eu au téléphone'),
    ('vous redéciderez ce jour-là', 'tu redécideras ce jour-là'),
    ('Marquez le devis ACCEPTÉ', 'Marque le devis ACCEPTÉ'),
)

# Mots qu'un lecteur non technicien ne doit jamais voir dans le guide.
MOTS_INTERDITS = ('endpoint', 'outcome', 'moteur', 'cadence réactive', 'API', 'JSON',
                  'backend', 'frontend', 'webhook', 'cadence')
# Exception : le NOM d'un écran existant.
EXCEPTIONS_MOTS = ('Cadences de relance',)


def adapter(texte: str) -> str:
    for source, cible in ADAPTATIONS:
        texte = texte.replace(source, cible)
    return texte


def typo(texte: str) -> str:
    """Typographie française : apostrophe courbe, espaces insécables."""
    t = texte.replace("'", '\u2019')
    t = re.sub(r'«\s', '«\u00a0', t)
    t = re.sub(r'\s»', '\u00a0»', t)
    t = re.sub(r'\s([:;?!])', '\u00a0\\1', t)
    return t


def esc(texte: str) -> str:
    """Texte -> HTML (échappé, typographié, espaces insécables en entités)."""
    return html.escape(typo(texte), quote=False).replace('\u00a0', '&nbsp;')


def esc_ecran(texte: str) -> str:
    """Comme ``esc`` ; les noms d'écran « entre guillemets » passent en gras."""
    resultat = esc(texte)
    return re.sub(r'(«&nbsp;.*?&nbsp;»)', r'<span class="ecran">\1</span>', resultat)


# ══════════════════════════════════════════════════════════════════════════════
# 3. LE SCHÉMA (SVG dessiné ici, aucune image externe)
# ══════════════════════════════════════════════════════════════════════════════

def _largeurs(groupes):
    table = {}
    for caracteres, largeur in groupes:
        for c in caracteres:
            table[c] = largeur
    return table


# Chasses de la Helvetica/Arial (millièmes d'em) — sert à vérifier que chaque
# texte du schéma tient dans sa boîte et que deux textes ne se chevauchent pas.
_LARGEURS_REG = _largeurs((
    ('\u2019\u2018ijl', 222), ("'", 191), (' \u00a0!,./:;I[\\]ft\u00b7', 278), ('()-r`', 333),
    ('"', 355), ('*', 389), ('\u00b0', 400), ('^', 469), ('ckJsvxyz', 500),
    ('0123456789abdeghnopqu_?\u00ab\u00bb\u2013', 556), ('+<=>~', 584), ('FTZ', 611),
    ('ABEKPSVXY&', 667), ('CDHNRUw', 722), ('GOQ', 778), ('mM', 833), ('%', 889),
    ('W\u0153', 944), ('\u2014\u2026\u2192\u0152', 1000), ('|', 260), ('{}', 334),
    ('@', 1015), ('L', 556),
))
_LARGEURS_GRAS = _largeurs((
    ('\u2019\u2018', 278), ("'", 238), (' \u00a0,./I[\\]', 278), ('!:;-()\u00b7', 333),
    ('"', 474), ('*', 389), ('\u00b0', 400), ('^', 584), ('z', 500),
    ('0123456789acksvxy_\u00ab\u00bb\u2013eJ', 556), ('+<=>~', 584),
    ('bdghnopqu', 611), ('?', 611), ('FTZ', 611), ('L', 611), ('EPSVXY&', 667), ('ABCDHKNRU', 722),
    ('GOQ', 778), ('w', 778), ('mM', 833), ('%', 889), ('m', 889), ('W\u0153', 944),
    ('\u2014\u2026\u2192\u0152', 1000), ('ij', 278), ('ft', 333), ('r', 389), ('l', 278),
    ('@', 975),
))


def mesurer(texte: str, taille: float, gras: bool = False) -> float:
    """Largeur estimée (unités du schéma) — marge de sécurité de 3 %."""
    table = _LARGEURS_GRAS if gras else _LARGEURS_REG
    total = 0
    for c in texte:
        base = c if c in table else unicodedata.normalize('NFD', c)[0]
        total += table.get(base, 556)
    return total * taille / 1000 * 1.03


COULEUR_VERT = '#0b3d2e'
COULEUR_ENCRE = '#1a1a1a'
COULEUR_ROUGE = '#8a2a22'
COULEUR_GRIS = '#4a4a4a'


class Schema:
    """Petit dessinateur SVG qui vérifie ce qu'il dessine : un texte trop large
    pour sa boîte, ou deux textes qui se recouvrent, arrêtent la génération."""

    def __init__(self, largeur: int):
        self.largeur = largeur
        self.formes: list[str] = []
        self.textes: list[tuple] = []  # (x0, y0, x1, y1, texte)

    # -- formes ---------------------------------------------------------------
    def rect(self, x, y, w, h, *, fill, stroke, sw=1.6, dash=None, rx=9):
        tirets = f' stroke-dasharray="{dash}"' if dash else ''
        self.formes.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{tirets}/>')

    def trait(self, points, *, couleur=COULEUR_VERT, sw=2.0, pointe=True, dash=None,
              marqueur='pointe'):
        chemin = ' '.join(('M' if i == 0 else 'L') + f'{x:.1f},{y:.1f}'
                          for i, (x, y) in enumerate(points))
        fin = f' marker-end="url(#{marqueur})"' if pointe else ''
        tirets = f' stroke-dasharray="{dash}"' if dash else ''
        self.formes.append(
            f'<path d="{chemin}" fill="none" stroke="{couleur}" stroke-width="{sw}" '
            f'stroke-linejoin="round"{tirets}{fin}/>')

    def point(self, x, y, r=3.6, couleur=COULEUR_VERT):
        self.formes.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{couleur}"/>')

    # -- textes ---------------------------------------------------------------
    def texte(self, x, base, s, taille, *, gras=False, ancre='middle', couleur=COULEUR_ENCRE,
              italique=False, dans=None):
        largeur = mesurer(s, taille, gras)
        x0 = {'middle': x - largeur / 2, 'start': x, 'end': x - largeur}[ancre]
        if dans is not None and (x0 < dans[0] - 0.01 or x0 + largeur > dans[1] + 0.01):
            raise ValueError(
                f'Schéma : « {s} » ({largeur:.0f}) ne tient pas dans sa boîte '
                f'({dans[1] - dans[0]:.0f}).')
        cadre = (x0, base - taille * 0.91, x0 + largeur, base + taille * 0.22, s)
        for autre in self.textes:
            if (cadre[0] < autre[2] and cadre[2] > autre[0]
                    and cadre[1] < autre[3] and cadre[3] > autre[1]):
                raise ValueError(f'Schéma : « {s} » chevauche « {autre[4]} ».')
        self.textes.append(cadre)
        attrs = f'font-size="{taille}" text-anchor="{ancre}" fill="{couleur}"'
        if gras:
            attrs += ' font-weight="700"'
        if italique:
            attrs += ' font-style="italic"'
        self.formes.append(f'<text x="{x:.1f}" y="{base:.1f}" {attrs}>{html.escape(typo(s), quote=False)}</text>')

    def boite(self, x, y, w, h, lignes, *, fill, stroke, sw=1.6, dash=None, rx=9, marge=6):
        """Un cadre et son texte centré. ``lignes`` : (texte, taille, gras, couleur)."""
        self.rect(x, y, w, h, fill=fill, stroke=stroke, sw=sw, dash=dash, rx=rx)
        hauteur = sum(t * 1.25 for _s, t, _g, _c in lignes)
        haut = y + (h - hauteur) / 2
        for s, taille, gras, couleur in lignes:
            self.texte(x + w / 2, haut + taille * 0.97, s, taille, gras=gras, couleur=couleur,
                       dans=(x + marge, x + w - marge))
            haut += taille * 1.25

    def etiquette(self, x, base_haute, lignes, *, ancre='middle', taille=11, couleur=COULEUR_GRIS):
        """Étiquette de flèche : plusieurs lignes empilées de haut en bas."""
        for i, s in enumerate(lignes):
            self.texte(x, base_haute + i * (taille + 1.6), s, taille, ancre=ancre,
                       couleur=couleur, italique=True)

    def svg(self, hauteur: float, titre: str) -> str:
        defs = (
            '<defs>'
            '<marker id="pointe" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="8" '
            'markerHeight="8" markerUnits="userSpaceOnUse" orient="auto">'
            f'<path d="M0,0 L10,5 L0,10 z" fill="{COULEUR_VERT}"/></marker>'
            '<marker id="pointe-sortie" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="8" '
            'markerHeight="8" markerUnits="userSpaceOnUse" orient="auto">'
            f'<path d="M0,0 L10,5 L0,10 z" fill="{COULEUR_ROUGE}"/></marker>'
            '</defs>')
        corps = '\n'.join(self.formes)
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.largeur} {hauteur:.0f}" '
            f'role="img" aria-label="{html.escape(titre, quote=True)}" '
            'font-family="Helvetica Neue, Arial, Helvetica, sans-serif">\n'
            f'{defs}\n{corps}\n</svg>')


def dessiner_parcours(table: dict, gabarits: dict) -> str:
    """Le parcours en un regard : la chaîne principale, la branche visite, les sorties."""
    exiger_etapes(table, ('contact_appel', 'devis', 'suivi_appel', 'planifier',
                          'confirmation', 'debrief', 'decider_suite', 'reveil_appel'))
    protocoles = gabarits['protocoles']
    contact, suivi, reveil = protocoles['contact'], protocoles['apres_devis'], protocoles['reveil']
    jours_contact = max(t['delai_jours'] for t in contact)
    jours_suivi = max(t['delai_jours'] for t in suivi)
    reveils = liste_fr(f'J{t["delai_jours"]}' for t in reveil)

    s = Schema(700)
    fond_etape, fond_sortie = '#eef5f1', '#fdf3f2'

    # ── rangée principale ────────────────────────────────────────────────────
    y0, h0 = 22, 92
    ym = y0 + h0 / 2
    w_pilule, w_boite, g0 = 62, 118, 26
    g = ((690 - 8) - (2 * w_pilule + 3 * w_boite + g0)) / 3
    x_lead = 8
    x_c = x_lead + w_pilule + g0
    x_d = x_c + w_boite + g
    x_s = x_d + w_boite + g
    x_ok = x_s + w_boite + g

    s.boite(x_lead, ym - 22, w_pilule, 44,
            [('Lead', 12.5, True, COULEUR_VERT), ('arrivé', 12.5, True, COULEUR_VERT)],
            fill='#ffffff', stroke=COULEUR_VERT, rx=22)
    s.boite(x_c, y0, w_boite, h0,
            [('PRISE DE', 13.5, True, COULEUR_VERT), ('CONTACT', 13.5, True, COULEUR_VERT),
             ('messages et appels', 11, False, COULEUR_ENCRE),
             (f'{jours_contact} jours', 11, False, COULEUR_ENCRE)],
            fill=fond_etape, stroke=COULEUR_VERT, sw=2)
    s.boite(x_d, y0, w_boite, h0,
            [('PRÉPARER ET', 13.5, True, COULEUR_VERT), ('ENVOYER LE', 13.5, True, COULEUR_VERT),
             ('DEVIS', 13.5, True, COULEUR_VERT), ('tâche possible', 10.5, False, COULEUR_ENCRE),
             ('dès maintenant', 10.5, False, COULEUR_ENCRE)],
            fill=fond_etape, stroke=COULEUR_VERT, sw=2)
    s.boite(x_s, y0, w_boite, h0,
            [('SUIVI DE', 13.5, True, COULEUR_VERT), ('PROPOSITION', 13.5, True, COULEUR_VERT),
             (f'{len(suivi)} touches', 11, False, COULEUR_ENCRE),
             (f'{jours_suivi} jours', 11, False, COULEUR_ENCRE)],
            fill=fond_etape, stroke=COULEUR_VERT, sw=2)
    s.boite(x_ok, ym - 22, w_pilule, 44, [('SIGNÉ', 13.5, True, '#ffffff')],
            fill=COULEUR_VERT, stroke=COULEUR_VERT, rx=22)

    # flèches de la rangée principale (+ étiquettes dans les intervalles)
    s.trait([(x_lead + w_pilule, ym), (x_c, ym)])
    s.trait([(x_c + w_boite, ym), (x_d, ym)])
    s.trait([(x_d + w_boite, ym), (x_s, ym)])
    s.trait([(x_s + w_boite, ym), (x_ok, ym)])
    gx1, gx2, gx3 = (x_c + w_boite + g / 2, x_d + w_boite + g / 2, x_s + w_boite + g / 2)
    s.etiquette(gx1, ym - 20, ['client', 'joint'])
    s.etiquette(gx2, ym - 20, ['devis', 'envoyé'])
    s.etiquette(gx3, ym - 20, ['devis', 'accepté'])

    # ── branche visite technique ─────────────────────────────────────────────
    yv, hv = y0 + h0 + 84, 104
    xv, wv = x_c, 690 - x_c
    s.rect(xv, yv, wv, hv, fill='#fafafa', stroke=COULEUR_GRIS, sw=1.4, dash='2 4')
    s.texte(xv + 12, yv + 21, 'VISITE TECHNIQUE', 13, gras=True, ancre='start', couleur=COULEUR_ENCRE)
    s.texte(xv + wv - 12, yv + 21, 'relances en attente : décalées après la visite, jamais annulées',
            10.5, ancre='end', couleur=COULEUR_GRIS, italique=True)
    etapes_visite = [('Planifier', 'la visite'), ('Confirmer', 'la veille'), ('La visite', 'sur place'),
                     ('Retour du', 'technicien'), ('Débrief :', 'rappeler le client')]
    largeur_interne = wv - 24
    w_sub = 93
    ecart = (largeur_interne - 5 * w_sub) / 4
    y_sub = yv + 34
    for i, (l1, l2) in enumerate(etapes_visite):
        x_sub = xv + 12 + i * (w_sub + ecart)
        s.boite(x_sub, y_sub, w_sub, 56,
                [(l1, 11.5, True, COULEUR_VERT), (l2, 10.5, False, COULEUR_ENCRE)],
                fill='#ffffff', stroke=COULEUR_VERT, sw=1.3, rx=7, marge=4)
        if i < 4:
            s.trait([(x_sub + w_sub, y_sub + 28), (x_sub + w_sub + ecart, y_sub + 28)], sw=1.5)

    bas_principal = y0 + h0
    # départ : « client joint » -> visite acceptée
    s.point(gx1, ym)
    s.trait([(gx1, ym), (gx1, yv)], sw=1.6)
    s.etiquette(gx1 - 7, yv - 45, ['visite', 'acceptée'], ancre='end')
    # retour vers le devis
    x_dc = x_d + w_boite / 2
    s.trait([(x_dc, yv), (x_dc, bas_principal)], sw=1.6)
    s.etiquette(x_dc + 7, yv - 45, ['devis à préparer', 'ou à modifier'], ancre='start')
    # aller-retour avec le suivi de proposition
    x_in = x_s + 26
    x_out = x_s + 92
    s.trait([(x_in, bas_principal), (x_in, yv)], sw=1.6)
    s.etiquette(x_in + 7, yv - 45, ['visite', 'acceptée'], ancre='start')
    s.trait([(x_out, yv), (x_out, bas_principal)], sw=1.6)
    s.etiquette(x_out + 7, yv - 45, ['le suivi', 'reprend'], ancre='start')

    # ── sorties ──────────────────────────────────────────────────────────────
    yp = yv + hv + 30
    s.texte(8, yp + 12, 'SORTIES — possibles depuis la prise de contact, le devis ou le suivi',
            12.5, gras=True, ancre='start', couleur=COULEUR_ROUGE)
    s.formes.append(f'<path d="M8,{yp + 20:.1f} H690" stroke="{COULEUR_ROUGE}" stroke-width="1" '
                    'stroke-dasharray="3 3" fill="none"/>')
    x_t, w_t = 8, 222
    x_m, w_m = 262, 160
    x_r, w_r = 492, 198
    hr = 46
    tr = dict(fill=fond_sortie, stroke=COULEUR_ROUGE, sw=1.5, dash='6 3')
    fleche = dict(couleur=COULEUR_ROUGE, sw=1.6, marqueur='pointe-sortie')
    encre = COULEUR_ENCRE

    # rangée A : le froid
    ya = yp + 32
    s.boite(x_t, ya, w_t, hr, [('Aucune réponse jusqu\u2019à', 11.5, False, encre),
                               ('la dernière touche', 11.5, False, encre)], **tr)
    s.boite(x_m, ya, w_m, hr, [('FROID', 13, True, COULEUR_ROUGE),
                               (f'réveils {reveils}', 11, False, encre)], **tr)
    s.boite(x_r, ya, w_r, hr, [('Le dossier sort du Froid :', 11.5, False, encre),
                               ('suivi ou devis à préparer', 11.5, False, encre)], **tr)
    s.trait([(x_t + w_t, ya + hr / 2), (x_m, ya + hr / 2)], **fleche)
    s.trait([(x_m + w_m, ya + hr / 2), (x_r, ya + hr / 2)], **fleche)
    s.etiquette((x_m + w_m + x_r) / 2, ya + hr / 2 - 21, ['si le client', 'répond'])

    # rangée B : le refus
    yb = ya + hr + 20
    h_cible = 34
    yb_centre = yb + (2 * h_cible + 10) / 2
    s.boite(x_t, yb_centre - hr / 2, w_t, hr, [('Le client refuse', 11.5, False, encre)], **tr)
    s.boite(x_m, yb_centre - hr / 2, w_m, hr, [('DÉCIDER LA SUITE', 12.5, True, COULEUR_ROUGE),
                                               ('tâche possible dès maintenant', 10, False, encre)], **tr)
    s.boite(x_r, yb, w_r, h_cible, [('PERDU', 12.5, True, COULEUR_ROUGE),
                                    ('avec son motif', 10.5, False, encre)], **tr)
    s.boite(x_r, yb + h_cible + 10, w_r, h_cible, [('RELANCE ULTÉRIEURE', 12.5, True, COULEUR_ROUGE),
                                                   ('à la date choisie', 10.5, False, encre)], **tr)
    s.trait([(x_t + w_t, yb_centre), (x_m, yb_centre)], **fleche)
    x_coude = (x_m + w_m + x_r) / 2
    s.trait([(x_m + w_m, yb_centre), (x_coude, yb_centre), (x_coude, yb + h_cible / 2), (x_r, yb + h_cible / 2)],
            **fleche)
    s.trait([(x_coude, yb_centre), (x_coude, yb + h_cible + 10 + h_cible / 2),
             (x_r, yb + h_cible + 10 + h_cible / 2)], **fleche)

    # rangée C : ne plus contacter
    yc = yb + 2 * h_cible + 10 + 20
    s.boite(x_t, yc, w_t, hr, [('\u00ab Ne plus me contacter \u00bb', 11.5, False, encre)], **tr)
    s.boite(x_m, yc, w_m, hr, [('NE PLUS CONTACTER', 12, True, COULEUR_ROUGE)], **tr)
    s.boite(x_r, yc, w_r, hr, [('Plus aucune relance,', 11.5, False, encre),
                               ('opposition inscrite au registre', 10.5, False, encre)], **tr)
    s.trait([(x_t + w_t, yc + hr / 2), (x_m, yc + hr / 2)], **fleche)
    s.trait([(x_m + w_m, yc + hr / 2), (x_r, yc + hr / 2)], **fleche)

    return s.svg(yc + hr + 8, 'Le parcours du suivi commercial : prise de contact, devis, suivi de '
                              'proposition, signature, avec la branche visite technique et les sorties.')


# ══════════════════════════════════════════════════════════════════════════════
# 4. LE DOCUMENT HTML
# ══════════════════════════════════════════════════════════════════════════════

CSS = """
@page { size: A4; margin: 18mm; @bottom-center { content: "TAQINOR OS — Guide interne · page " counter(page) "/" counter(pages); font-family: 'Helvetica Neue', Arial, sans-serif; font-size: 8pt; color: #888; } }
* { box-sizing: border-box; }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { font-family: 'Helvetica Neue', Arial, sans-serif; font-size: 10.5pt; color: #1a1a1a; line-height: 1.42; margin: 0; }
h1 { font-size: 20pt; color: #0b3d2e; margin: 0 0 2mm; line-height: 1.15; }
.sous-titre { color: #555; font-size: 10.5pt; margin: 0 0 1mm; }
.version { color: #555; font-size: 9.5pt; margin: 0 0 4mm; }
.lede { font-size: 10.5pt; margin: 0 0 2mm; }
h2 { font-size: 14pt; color: #0b3d2e; border-bottom: 1.5pt solid #0b3d2e; padding-bottom: 1mm; margin: 8mm 0 3mm; break-after: avoid; page-break-after: avoid; }
h2.nouvelle-page { break-before: page; page-break-before: always; margin-top: 0; }
p, li { margin: 0 0 1.8mm; }
ul, ol { margin: 0 0 2mm; padding-left: 6mm; }
.encadre { background: #f0f6f3; border-left: 3pt solid #0b3d2e; padding: 3mm 4mm; margin: 3mm 0; break-inside: avoid; page-break-inside: avoid; }
.encadre ul, .encadre ol { margin-bottom: 0; }
.encadre li:last-child { margin-bottom: 0; }
.ecran { font-weight: 600; }
.bloc { break-inside: avoid; page-break-inside: avoid; }
table { border-collapse: collapse; width: 100%; margin: 2mm 0 4mm; font-size: 9.5pt; line-height: 1.35; }
th, td { border: 0.5pt solid #bbb; padding: 1mm 2.4mm; text-align: left; vertical-align: top; }
th { background: #0b3d2e; color: #fff; font-weight: 600; }
tr { break-inside: avoid; page-break-inside: avoid; }
.petit { font-size: 9pt; color: #666; }
figure { margin: 2mm 0 3mm; break-inside: avoid; page-break-inside: avoid; }
figure svg { display: block; width: 100%; height: auto; }
figcaption { font-size: 8.5pt; color: #555; margin-top: 1.5mm; }
.famille { break-before: page; page-break-before: always; }
.famille-titre { font-size: 15pt; color: #fff; background: #0b3d2e; border-radius: 1.5mm; padding: 2mm 4mm; margin: 0 0 3mm; break-after: avoid; page-break-after: avoid; }
.rythmes-titre { font-size: 12.5pt; color: #0b3d2e; margin: 4mm 0 1mm; break-after: avoid; page-break-after: avoid; }
.rythme { break-inside: avoid; page-break-inside: avoid; margin: 0 0 3mm; }
.rythme h4 { font-size: 11pt; color: #0b3d2e; margin: 3mm 0 0.5mm; break-after: avoid; page-break-after: avoid; }
.rythme p { margin-bottom: 1mm; }
table.touches { width: 100%; margin: 1mm 0 1.5mm; font-size: 9pt; line-height: 1.25; }
table.touches th, table.touches td { padding: 0.5mm 2.4mm; }
table.touches td:nth-child(1) { width: 9%; }
table.touches td:nth-child(2) { width: 17%; }
table.touches td:nth-child(3) { width: 17%; }
.fiche { margin: 0 0 5mm; break-inside: avoid; page-break-inside: avoid; }
.fiche-tete { background: #f0f6f3; border-left: 3pt solid #0b3d2e; padding: 2mm 4mm 1.8mm; }
.fiche-tete h4 { margin: 0; font-size: 11.5pt; color: #0b3d2e; line-height: 1.3; }
.badge { float: right; font-size: 8pt; font-weight: 600; color: #0b3d2e; background: #fff; border: 0.5pt solid #0b3d2e; border-radius: 3mm; padding: 0.2mm 2.4mm; margin-left: 3mm; }
.exemples { font-size: 8.5pt; color: #666; margin: 0.6mm 0 0; }
.question { margin: 1.4mm 0 0; font-size: 10pt; }
.question .q { font-weight: 700; color: #0b3d2e; }
.aide { margin: 1.2mm 0 0; font-size: 9pt; color: #444; }
.fiche table { margin: 0; }
.fiche th:nth-child(1), .fiche td:nth-child(1) { width: 31%; }
.pastille { display: inline-block; font-size: 7.5pt; font-weight: 400; color: #555; border: 0.4pt solid #aaa; border-radius: 2mm; padding: 0 1.6mm; margin: 0.4mm 0 0 1.4mm; white-space: nowrap; }
.note { font-size: 9pt; color: #555; margin: 1.5mm 0 0; }
.pied { margin-top: 8mm; padding-top: 2mm; border-top: 0.5pt solid #bbb; font-size: 9pt; color: #666; break-inside: avoid; page-break-inside: avoid; }
"""

REGLES = (
    'Un dossier actif a toujours une prochaine étape.',
    'Avant de confirmer, l\u2019écran te dit ce que la réponse va déclencher.',
    'Un geste réellement fait se note toujours, même s\u2019il est fait en avance sur sa date.',
    'Les tâches (par exemple préparer le devis, planifier la visite, décider la suite) se traitent dès '
    'maintenant : inutile d\u2019attendre leur date.',
    'Rien ne part tout seul vers le client : c\u2019est toujours ton clic.',
    '\u00ab Perdu \u00bb est ta décision, avec son motif \u2014 jamais un effet de bord.',
)

# Ce qui a changé le 30/09/2026 (8 lignes au plus) — écrit en français simple
# à partir des constats de la correction du suivi : (mot d'appel, phrase).
CHANGEMENTS = (
    ('Appel fait en avance.',
     'L\u2019issue d\u2019un appel passé en avance sur sa date se saisit maintenant, comme pour '
     'n\u2019importe quel appel.'),
    ('Étape du devis.',
     '\u00ab Préparer et envoyer le devis \u00bb se traite le jour même : elle est posée pour '
     'demain, mais rien ne t\u2019oblige à attendre.'),
    ('Fenêtre de planification.',
     'Elle ne disparaît plus : elle s\u2019ouvre avant tout enregistrement, et si tu annules, '
     'rien n\u2019est enregistré.'),
    ('Envoi du devis.',
     'Envoyer le devis démarre le suivi de proposition, même si une visite est en cours.'),
    ('Décider la suite.',
     'L\u2019étape propose \u00ab Perdu \u2014 clore le dossier \u00bb, avec son motif ; un refus ne la '
     'repose plus en boucle.'),
    ('Visite refusée.',
     'Refuser ou annuler la visite n\u2019arrête plus tout le suivi : le rendez-vous est annulé, '
     'le suivi continue sans visite.'),
    ('Visite reportée.',
     'Reporter une visite la déplace : elle n\u2019est jamais doublée.'),
    ('Fiche du lead.',
     'Après avoir cliqué sur \u00ab Appeler \u00bb, tu peux saisir l\u2019issue de l\u2019appel '
     'directement depuis la fiche du lead.'),
)

OU_TROUVER = (
    ('Les touches du jour, tous leads confondus', 'Cockpit CRM \u2192 \u00ab Relances du jour \u00bb'),
    ('Toutes les touches, jour par jour', 'Menu CRM \u2192 \u00ab Suivi des relances \u00bb'),
    ('Les étapes et les réponses d\u2019un lead', 'Fiche du lead \u2192 section \u00ab Suivi commercial \u00bb'),
    ('Les délais et les messages du suivi',
     'Paramètres \u2192 Référentiels \u2192 \u00ab Cadences de relance \u00bb'),
    ('Ce guide', 'Documents (GED) \u2192 cabinet \u00ab Documentation \u00bb \u2192 dossier \u00ab Guides \u00bb'),
    ('Le guide de la visite technique',
     'Même dossier : \u00ab Guide \u2014 La visite technique dans le suivi commercial \u00bb'),
)


def bloc(contenu: str) -> str:
    """Une section (titre + tableau) qui ne se coupe jamais entre deux pages."""
    return '<section class="bloc">\n' + contenu + '\n</section>'


def html_couverture(table: dict) -> str:
    return (
        '<header>\n'
        '<h1>Le suivi commercial : étapes, réponses et suites</h1>\n'
        '<p class="sous-titre">Guide interne équipe commerciale \u00b7 TAQINOR</p>\n'
        f'<p class="version">Version {esc(table["version"])} \u00b7 {date_fr(table["maj"])}</p>\n'
        '<p class="lede">Pour chaque étape du suivi : la question qui t\u2019est posée, les réponses '
        'possibles, et ce que chaque réponse déclenche ensuite.</p>\n'
        '</header>')


def html_parcours(table: dict, gabarits: dict) -> str:
    return (
        '<h2>1. Le parcours en un regard</h2>\n'
        '<figure>\n' + dessiner_parcours(table, gabarits) + '\n'
        '<figcaption>Lecture : cadre plein = étape \u00b7 cadre en tirets = sortie \u00b7 '
        'flèche = ce qui se passe ensuite \u00b7 tâche = possible dès maintenant.</figcaption>\n'
        '</figure>')


NOMBRES_EN_LETTRES = {2: 'deux', 3: 'trois', 4: 'quatre', 5: 'cinq', 6: 'six', 7: 'sept',
                      8: 'huit', 9: 'neuf', 10: 'dix'}


def html_regles() -> str:
    """Les règles du suivi ; le titre compte les règles réellement listées."""
    nombre = NOMBRES_EN_LETTRES.get(len(REGLES), str(len(REGLES)))
    items = '\n'.join(f'<li>{esc(r)}</li>' for r in REGLES)
    return (f'<h2>2. Les {nombre} règles</h2>\n<div class="encadre">\n<ol>\n' + items
            + '\n</ol>\n</div>')


def html_boutons(table: dict) -> str:
    lignes = ['<h2>3. Les boutons d\u2019une étape</h2>', '<table>',
              '<tr><th style="width:24%">Bouton</th><th>Ce qu\u2019il fait</th></tr>']
    for g in table['gestes']:
        lignes.append(f'<tr><td><strong>{esc(g["label"])}</strong></td>'
                      f'<td>{esc_ecran(adapter(g["effet"]))}</td></tr>')
    lignes.append('</table>')
    return '\n'.join(lignes)


def html_touches(touches: list, canaux: dict, depart: str = '') -> str:
    lignes = ['<table class="touches">',
              '<tr><th>N\u00b0</th><th>Jour</th><th>Canal</th><th>Touche</th></tr>']
    for t in touches:
        lignes.append(
            f'<tr><td>{t["ordre"]}</td><td>{esc(jour_lisible(t))}</td>'
            f'<td>{esc(canaux.get(t["canal"], t["canal"]))}</td><td>{esc(t["libelle"])}</td></tr>')
    lignes.append('</table>')
    if depart:
        lignes.append(f'<p class="petit">{esc(depart)}</p>')
    return '\n'.join(lignes)


def phrase_protocole(touches: list, canaux_appel: str = 'appel') -> str:
    appels = sum(1 for t in touches if t['canal'] == canaux_appel)
    messages = len(touches) - appels
    jours = max(t['delai_jours'] for t in touches)
    return (f'{len(touches)} touches — {pluriel(appels, "appel", "appels")} et '
            f'{pluriel(messages, "message", "messages")} — sur {jours} jours.')


# protocole (cadence des gabarits) -> phrase qui dit d'où part « J0 »
DEPART_DU_PROTOCOLE = {
    'contact': 'J0 = l’arrivée du lead.',
    'apres_devis': 'J0 = l’envoi du devis.',
    'reveil': '',
}


def protocole_de_famille(etapes: list) -> str | None:
    """Le protocole (contact, apres_devis, reveil) que suivent les étapes d'une
    famille, d'après leur reconnaissance dans la table — jamais d'après le nom."""
    for etape in etapes:
        for cadence in etape.get('reconnaissance', {}).get('cadences', []):
            if cadence in DEPART_DU_PROTOCOLE:
                return cadence
    return None


def html_fiche(table: dict, etape: dict) -> str:
    tete = ['<div class="fiche">', '<div class="fiche-tete">']
    badge = '<span class="badge">Tâche : possible dès maintenant</span>' if etape.get('tache') else ''
    tete.append(f'<h4>{badge}{esc(etape["nom"])}</h4>')
    if etape.get('exemples'):
        exemples = ' \u00b7 '.join(etape['exemples'])
        tete.append(f'<p class="exemples">Exemples : {esc(exemples)}</p>')
    tete.append(f'<p class="question"><span class="q">Question posée</span> \u2014 {esc(etape["question"])}</p>')
    if etape.get('aide'):
        tete.append(f'<p class="aide">{esc_ecran(adapter(etape["aide"]))}</p>')
    tete.append('</div>')
    lignes = tete + ['<table>', '<tr><th>Ta réponse</th><th>Ce qui se passe ensuite</th></tr>']
    # Les réponses d'APPEL décrites par la table (étape générique) : des lignes à part
    # entière, insérées après la première réponse comme à l'écran ; celles sans effet
    # restent une simple mention.
    lignes_appel, sans_effet = [], []
    for entree in etape.get('reponses_appel', ()):
        entree = entree if isinstance(entree, dict) else {'modele': entree}
        modele = table['modeles'].get(entree['modele'])
        if not modele:
            continue
        r = {**modele, **entree}
        if r.get('effet'):
            lignes_appel.append(
                f'<tr><td><strong>{esc(r["label"])}</strong>'
                '<span class="pastille">sur un appel</span></td>'
                f'<td>{esc_ecran(adapter(r["effet"]))}</td></tr>')
        else:
            sans_effet.append(r['label'])
    for rang, r in enumerate(reponses_resolues(table, etape)):
        if rang == 1:
            lignes.extend(lignes_appel)
        pastilles = ''
        if r.get('date'):
            pastilles += '<span class="pastille">date à saisir</span>'
        if r.get('motif_perte'):
            pastilles += '<span class="pastille">motif à choisir</span>'
        if r.get('motif_refus'):
            pastilles += '<span class="pastille">motif de refus, facultatif</span>'
        if r.get('geste'):
            pastilles += '<span class="pastille">ouvre la planification</span>'
        lignes.append(f'<tr><td><strong>{esc(r["label"])}</strong>{pastilles}</td>'
                      f'<td>{esc_ecran(adapter(r["effet"]))}</td></tr>')
    if len(lignes_appel) and len(reponses_resolues(table, etape)) < 2:
        lignes.extend(lignes_appel)
    lignes.append('</table>')
    if sans_effet:
        liste = ' · '.join(sans_effet)
        lignes.append(f'<p class="note">Sur une étape d’appel, {len(sans_effet)} réponses s’ajoutent : '
                      f'{esc(liste)}.</p>')
    lignes.append('</div>')
    return '\n'.join(lignes)


def regrouper_par_famille(table: dict) -> dict:
    familles: dict = {}
    for etape in table['etapes']:
        familles.setdefault(etape['famille'], []).append(etape)
    return familles


def html_rythmes(gabarits: dict, familles: dict) -> str:
    """Le rythme des touches : un petit tableau par protocole, lu dans les gabarits."""
    blocs = ['<div class="rythmes">',
             '<h3 class="rythmes-titre">Le rythme des touches</h3>',
             '<p>Ces délais sont les réglages par défaut ; ils se modifient dans '
             + esc_ecran('Paramètres → Référentiels → « Cadences de relance ».') + '</p>']
    for nom, etapes in familles.items():
        cle = protocole_de_famille(etapes)
        if not cle:
            continue
        touches = gabarits['protocoles'][cle]
        blocs.append('<section class="rythme">')
        blocs.append(f'<h4>{esc(nom)}</h4>')
        if cle == 'reveil':
            jours = liste_fr('J' + str(t['delai_jours']) for t in touches)
            blocs.append(f'<p>{pluriel(len(touches), "réveil", "réveils")} : {esc(jours)}.</p>')
        else:
            blocs.append(f'<p>{esc(phrase_protocole(touches))}</p>')
        blocs.append(html_touches(touches, gabarits['canaux'], DEPART_DU_PROTOCOLE[cle]))
        blocs.append('</section>')
    blocs.append('</div>')
    return '\n'.join(blocs)


def html_etapes(table: dict, gabarits: dict) -> str:
    familles = regrouper_par_famille(table)
    blocs = ['<h2 class="nouvelle-page">4. Étape par étape</h2>',
             '<p>D\u2019abord le rythme des touches, puis une fiche par type d\u2019étape : la question '
             'posée, chaque réponse et ce qui se passe ensuite. Les mentions en petit signalent une '
             'réponse qui demande une date, un motif, ou qui ouvre la planification.</p>',
             html_rythmes(gabarits, familles)]
    for nom, etapes in familles.items():
        blocs.append('<section class="famille">')
        blocs.append(f'<h3 class="famille-titre">{esc(nom)}</h3>')
        for etape in etapes:
            blocs.append(html_fiche(table, etape))
        blocs.append('</section>')
    return '\n'.join(blocs)


def html_evenements(table: dict) -> str:
    lignes = ['<h2>5. Ce qui se fait tout seul</h2>',
              '<p>Ces événements déclenchent des actions sans que tu aies à intervenir.</p>',
              '<table>', '<tr><th style="width:34%">Quand</th><th>Ce que fait l\u2019ERP</th></tr>']
    for ev in table['evenements']:
        lignes.append(f'<tr><td>{esc_ecran(adapter(ev["quand"]))}</td>'
                      f'<td>{esc_ecran(adapter(ev["effet"]))}</td></tr>')
    lignes.append('</table>')
    return '\n'.join(lignes)


LIGNES_MAX_CHANGEMENTS = 8  # consigne : l'encadré « ce qui a changé » reste court


def html_changements() -> str:
    if len(CHANGEMENTS) > LIGNES_MAX_CHANGEMENTS:
        erreur(f'« Ce qui a changé » ne doit pas dépasser {LIGNES_MAX_CHANGEMENTS} lignes '
               f'({len(CHANGEMENTS)} écrites).')
    items = '\n'.join(f'<li><strong>{esc(mot)}</strong> {esc_ecran(phrase)}</li>'
                      for mot, phrase in CHANGEMENTS)
    return (f'<h2>6. Ce qui a changé le {DATE_CHANGEMENTS}</h2>\n<div class="encadre">\n<ul>\n'
            + items + '\n</ul>\n</div>')


def html_ou_trouver() -> str:
    lignes = ['<h2>7. Où trouver quoi</h2>', '<table>',
              '<tr><th style="width:42%">Quoi</th><th>Où</th></tr>']
    for quoi, ou in OU_TROUVER:
        lignes.append(f'<tr><td>{esc(quoi)}</td><td>{esc_ecran(ou)}</td></tr>')
    lignes.append('</table>')
    return '\n'.join(lignes)


def html_pied(table: dict) -> str:
    return ('<p class="pied">Version ' + esc(table['version']) + ' \u2014 ' + date_fr(table['maj'])
            + ' \u2014 généré depuis la table du parcours ; chaque réponse est rejouée par la garde de parcours (hors cas « dernière touche ») à '
            'chaque mise à jour de l\u2019ERP.</p>')


def produire_html(racine: Path = RACINE):
    """``(html, empreinte_table, table, gabarits)`` — fonction PURE du dépôt."""
    c = chemins(racine)
    table, empreinte = lire_table(c.table)
    valider_table(table)
    gabarits = lire_gabarits(c.gabarits)
    titre = TITRE_GED
    document = '\n'.join([
        '<!DOCTYPE html>',
        '<html lang="fr">',
        '<head>',
        '<meta charset="utf-8">',
        f'<title>{esc(titre)}</title>',
        '<meta name="generator" content="scripts/generer_guide_suivi.py">',
        f'<meta name="table-version" content="{html.escape(str(table["version"]), quote=True)}">',
        f'<meta name="table-sha256" content="{empreinte}">',
        '<!-- Fichier GÉNÉRÉ : ne pas modifier à la main. Relancer '
        '`python scripts/generer_guide_suivi.py` après tout changement de la table du parcours. -->',
        '<style>' + CSS + '</style>',
        '</head>',
        '<body>',
        html_couverture(table),
        html_parcours(table, gabarits),
        html_regles(),
        bloc(html_boutons(table)),
        html_etapes(table, gabarits),
        bloc(html_evenements(table)),
        bloc(html_changements()),
        bloc(html_ou_trouver()),
        html_pied(table),
        '</body>',
        '</html>',
    ]) + '\n'
    return document, empreinte, table, gabarits


def texte_visible(document: str) -> str:
    """Le texte lisible d'un document HTML (sans balises ni styles)."""
    sans_style = re.sub(r'<style>.*?</style>|<svg.*?</svg>|<!--.*?-->', ' ', document, flags=re.S)
    return html.unescape(re.sub(r'<[^>]+>', ' ', sans_style))


def verifier_langage(document: str) -> list:
    """Mots techniques encore visibles dans le guide (avertissement, pas un échec)."""
    texte = texte_visible(document)
    for exception in EXCEPTIONS_MOTS:
        texte = texte.replace(exception, ' ')
    trouves = []
    for mot in MOTS_INTERDITS:
        for m in re.finditer(r'\b' + re.escape(mot) + r'\b', texte, flags=re.I if mot != 'API' else 0):
            trouves.append((mot, ' '.join(texte[max(0, m.start() - 40):m.end() + 40].split())))
    return trouves


# ══════════════════════════════════════════════════════════════════════════════
# 5. ÉCRITURE, MANIFESTE ET IMPRESSION PAR EDGE
# ══════════════════════════════════════════════════════════════════════════════

def ecrire_texte_si_change(chemin: Path, contenu: str) -> bool:
    """Écrit ``contenu`` (UTF-8, LF) si le fichier diffère ; renvoie True si écrit."""
    if chemin.is_file():
        try:
            if normaliser_lf(chemin.read_text(encoding='utf-8')) == contenu:
                return False
        except (OSError, UnicodeDecodeError):
            pass
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with open(chemin, 'w', encoding='utf-8', newline='\n') as f:
        f.write(contenu)
    return True


def maj_manifeste(chemin: Path, version: str) -> bool:
    """Crée ou met à jour l'entrée de CE guide dans le manifeste de publication."""
    try:
        donnees = json.loads(chemin.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        erreur(f'Manifeste illisible ({chemin}) : {exc}')
    if not isinstance(donnees, list):
        erreur(f'Manifeste invalide (liste attendue) : {chemin}')
    entree = {'fichier': FICHIER_PDF, 'titre': TITRE_GED, 'version': str(version),
              'description': DESCRIPTION_GED, 'cabinet': CABINET_GED, 'dossier': DOSSIER_GED}
    for i, existante in enumerate(donnees):
        if isinstance(existante, dict) and existante.get('fichier') == FICHIER_PDF:
            donnees[i] = entree
            break
    else:
        donnees.append(entree)
    return ecrire_texte_si_change(chemin, json.dumps(donnees, indent=2, ensure_ascii=False) + '\n')


def trouver_edge(demande: str | None) -> Path:
    if demande:
        chemin = Path(demande)
        if chemin.is_file():
            return chemin
        erreur(f'Edge introuvable : {demande}')
    for candidat in EDGE_CANDIDATS:
        if Path(candidat).is_file():
            return Path(candidat)
    for nom in ('msedge', 'microsoft-edge', 'microsoft-edge-stable'):
        trouve = shutil.which(nom)
        if trouve:
            return Path(trouve)
    erreur('Edge introuvable : indiquez son chemin avec --edge, ou utilisez --html-seulement.')


def imprimer_pdf(edge: Path, source_html: Path, destinations: list) -> int:
    """Imprime ``source_html`` en PDF avec Edge sans tête ; copie le PDF vers
    chaque destination (octet pour octet). Renvoie la taille du PDF."""
    profil = tempfile.mkdtemp(prefix='edge-guide-profil-')
    sortie = tempfile.mkdtemp(prefix='edge-guide-pdf-')
    pdf_temporaire = Path(sortie) / 'sortie.pdf'
    commande = [str(edge), '--headless=new', '--disable-gpu', '--no-pdf-header-footer',
                f'--user-data-dir={profil}', '--no-first-run',
                f'--print-to-pdf={pdf_temporaire}', source_html.resolve().as_uri()]
    try:
        try:
            resultat = subprocess.run(commande, capture_output=True, timeout=DELAI_IMPRESSION)
        except subprocess.TimeoutExpired:
            erreur(f'Edge n\u2019a pas fini d\u2019imprimer {source_html.name} en {DELAI_IMPRESSION} s.', 1)
        except OSError as exc:
            erreur(f'Edge n\u2019a pas pu être lancé ({edge}) : {exc}', 1)
        # Edge peut rendre la main un instant avant que le fichier soit complet.
        fin = time.monotonic() + 15
        taille = -1
        while time.monotonic() < fin:
            if pdf_temporaire.is_file():
                nouvelle = pdf_temporaire.stat().st_size
                if nouvelle > 0 and nouvelle == taille:
                    break
                taille = nouvelle
            time.sleep(0.4)
        if not pdf_temporaire.is_file():
            erreur(f'Edge n\u2019a écrit aucun PDF pour {source_html.name} (code {resultat.returncode}).', 1)
        donnees = pdf_temporaire.read_bytes()
        if not donnees.startswith(b'%PDF') or len(donnees) < TAILLE_PDF_MINI:
            erreur(f'Le PDF de {source_html.name} est invalide ou trop petit ({len(donnees)} octets).', 1)
        for destination in destinations:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(donnees)
        return len(donnees)
    finally:
        for dossier in (profil, sortie):
            for _essai in range(5):
                shutil.rmtree(dossier, ignore_errors=True)
                if not Path(dossier).exists():
                    break
                time.sleep(0.5)


def main(argv=None) -> int:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    analyseur = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    analyseur.add_argument('--html-seulement', action='store_true',
                           help='n\u2019écrit que le HTML et le manifeste (machine sans Edge)')
    analyseur.add_argument('--forcer', action='store_true',
                           help='réimprime le PDF même si le HTML n\u2019a pas changé')
    analyseur.add_argument('--visite', action='store_true',
                           help='réimprime aussi le guide de la visite technique (deux PDF identiques)')
    analyseur.add_argument('--edge', default=None, help='chemin de msedge.exe')
    args = analyseur.parse_args(argv)
    if args.html_seulement and args.visite:
        erreur('--visite a besoin d\u2019Edge : incompatible avec --html-seulement.')

    c = chemins()
    # Edge d'abord : sans lui (et sans --html-seulement) on s'arrête avant de
    # toucher au moindre fichier, plutôt que de laisser un état à moitié fait.
    edge = None if args.html_seulement else trouver_edge(args.edge)
    document, empreinte, table, _gabarits = produire_html()
    for mot, contexte in verifier_langage(document):
        print(f'ATTENTION langage : « {mot} » encore visible : … {contexte} …', file=sys.stderr)

    html_change = ecrire_texte_si_change(c.html, document)
    print(('HTML écrit' if html_change else 'HTML déjà à jour') + f' : {c.html.relative_to(RACINE)} '
          f'(table {table["version"]}, empreinte {empreinte[:12]}…)')
    if maj_manifeste(c.manifeste, table['version']):
        print(f'Manifeste mis à jour : {c.manifeste.relative_to(RACINE)}')
    else:
        print('Manifeste déjà à jour.')

    if args.html_seulement:
        print('Option --html-seulement : le PDF n\u2019a PAS été régénéré.')
        return 0

    if args.forcer or html_change or not c.pdf.is_file():
        taille = imprimer_pdf(edge, c.html, [c.pdf])
        print(f'PDF imprimé : {c.pdf.relative_to(RACINE)} ({taille} octets)')
    else:
        print('PDF déjà à jour (HTML inchangé) : rien à imprimer (--forcer pour le réimprimer).')
    if args.visite:
        taille = imprimer_pdf(edge, c.visite_html, [c.visite_pdf_docs, c.visite_pdf_fixture])
        print(f'Guide de la visite imprimé ({taille} octets) : {c.visite_pdf_docs.relative_to(RACINE)} '
              f'et {c.visite_pdf_fixture.relative_to(RACINE)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
