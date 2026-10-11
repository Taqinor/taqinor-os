#!/usr/bin/env python3
"""ENF (décision fondateur D1 du 09/10/2026) — tout paramètre de requête que le
FRONTEND envoie est DÉCLARÉ par l'opération OpenAPI qu'il frappe.

POURQUOI CETTE GARDE EXISTE
---------------------------
``core/parametres_requete.py`` (ENFP) refuse côté serveur (400
``unknown_query_parameter``) tout ``?x=`` que le schéma OpenAPI de l'opération
ne déclare pas (réglage ``API_QUERY_PARAMS_STRICT``). Avant de l'allumer en
tests/CI puis en production, il faut la PREUVE que l'écran n'envoie jamais un
paramètre non déclaré — sinon l'allumage casse un écran en silence. Cette garde
est cette preuve, et elle reste en place pour qu'un nouvel appel ne la défasse
pas.

SOURCE DU CONTRAT
-----------------
``docs/openapi-schema.yml`` (instantané versionné, régénéré par
``check_openapi_schema.py --write``) porte une section ``query_params:`` : les
paramètres ``in: query`` que drf-spectacular déclare pour chaque opération —
exactement l'ensemble que ENFP accepte (+ ``format``, honoré par DRF partout).
La dérive de cette section est BLOQUANTE dans ``backend-openapi`` (PACT6) :
l'instantané ne peut pas mentir sur le code.

EXTRACTION (analyse statique pure, stdlib seule, < 30 s)
-------------------------------------------------------
Tout ``frontend/src`` hors tests (même périmètre que ``check_api_contract.py``,
dont on réutilise le lexeur : commentaires retirés, chaînes masquées).

1. Appels du client partagé : ``<client>.get|delete|head|options(url, config)``,
   ``<client>.post|put|patch(url, data, config)``. L'URL est résolue comme le
   fait ``check_api_contract.py`` (constantes, gabarits, ternaires de suffixe) ;
   sa CHAÎNE DE REQUÊTE est lue (``?a=${x}&b=1`` → ``a``, ``b`` ; ``?${qs}`` →
   ``qs`` suivi jusqu'à son ``URLSearchParams``).
2. ``config.params`` : littéral objet (clés, raccourcis, ternaires, ``||``/``??``,
   étalements suivis), variable locale (initialiseur + mutations
   ``p.x = …``, ``p['x'] = …``, ``p.set('x', …)``, ``Object.assign(p, {…})``).
3. PASSE-PLAT : quand ``params`` (ou la config entière) est un PARAMÈTRE de la
   fonction englobante (``getRules: (params) => api.get(u, { params })``), la
   garde remonte à TOUS les appelants de cette fonction (``crmApi.getRules({…})``)
   et résout leur argument, récursivement (profondeur 5). Un nom de fonction
   défini dans plusieurs modules n'est rattaché qu'aux appelants qui importent
   le module qui le définit.
   Une fonction PASSÉE sans être appelée est suivie : argument d'une fonction
   d'ordre supérieur du frontend (``toutesLesPages(gedApi.getX, { actif: 1 })``
   — ses paramètres sont LIÉS aux arguments de CE site), prop JSX
   (``<Editeur loadFn={savApi.getX} />``), ref React (``useRef(fetcher)`` puis
   ``ref.current(p)``), alias (``const fn = api.x``), ``useCallback`` /
   ``createAsyncThunk`` (y compris rendu par une fabrique de thunks) ; une
   expression ``f(args)`` / ``useMemo(() => …)`` est lue par ses ``return``.
   Une URL paramètre d'une fonction est suivie jusqu'à chaque appelant.
4. Fabrique CRUD partagée (``makeResourceFactory``) : ``<clé>.list(params)``
   devient un ``GET <base>/<slug>/`` (modèle dédié, ``_fabriques``).
5. Liens directs : un littéral ``/api/django/…?x=`` hors appel (``window.open``,
   ``href``) est un GET comme un autre.
6. Intercepteur global : ``frontend/src/api/axios.js`` pose ``?entite=`` sur les
   GET des listes de ``ENDPOINTS_ENTITE`` — la liste est RELUE dans axios.js
   (jamais recopiée ici), donc le modèle suit le code.

Le lexeur est celui de ``check_api_contract.py`` corrigé pour le texte JSX
(une apostrophe collée à une lettre n'ouvre pas de chaîne : sans cela,
``l'automatisation`` masquait tout le fichier et ses appels disparaissaient).

Ce qui ne se résout pas statiquement (expression calculée, fonction passée à
une bibliothèque, clé calculée, chemin non rattachable…) n'est JAMAIS ignoré :
il part dans la liste « NON RÉSOLU », qui échoue comme un constat. Remède :
rendre l'appel lisible, ou poser à côté une DÉCLARATION STATIQUE que la garde
lit, sur la ligne concernée ou l'une des lignes au-dessus :

    // parametres-requete: page, page_size, search
    // chemins-requete: /calepinage/calepinages/{id}/rapport-etude.pdf/

(la seconde pour une URL servie par le serveur, jamais construite côté écran).
Les noms et chemins déclarés sont VÉRIFIÉS contre le schéma comme les autres :
c'est une déclaration, pas une exemption.

ANGLES MORTS ASSUMÉS (documentés, pas silencieux)
-------------------------------------------------
* Un chemin qui ne correspond à aucune opération du schéma (route inconnue,
  FastAPI ``/api/fastapi``) n'est pas jugé ici — c'est le domaine de
  ``check_api_contract.py``. Il est listé (« hors schéma ») par ``--stats``.
* Un segment dynamique qui correspond à plusieurs gabarits également précis :
  l'union de leurs paramètres est acceptée.
* Rattachement des appelants par QUALIFICATIF (``parent.nom(``, ``<x>Api.nom(``,
  imports résolus) : un appelant atteint par un détour non modélisé
  (déstructuration ``const { getX } = api`` puis ``getX(p)``) n'est pas vu ;
  la fonction paraît alors sans appelant.
* Seuls les clients dont le nom évoque une API (``api``, ``client``, ``http``,
  ``axios``, ``instance``) sont lus ; ``api.request({...})`` n'est pas modélisé
  (aucune occurrence au 09/10/2026).
* Les fichiers de test (``.test.``/``.spec.``) ne joignent pas le serveur.

BASE D'EXCEPTIONS : ``scripts/frontend_query_params_allow.txt`` — VIDE par
construction ; chaque ligne y exige une raison, et la liste ne peut que
rétrécir (une entrée devenue inutile fait échouer la garde).

Usage :
    python scripts/check_frontend_query_params.py
    python scripts/check_frontend_query_params.py --stats
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_api_contract import (  # noqa: E402
    ANY, HOLE, FrontendCalls, frontend_files, normalise_call, resolve_template,
)

TYPE_DE_CLE = "par_symbole"  # AMET100 — cle de contenu `ECHEC|fichier|METHODE|operation|nom` (jamais un numero de ligne)

SNAPSHOT_PATH = ROOT / "docs" / "openapi-schema.yml"
ALLOW_PATH = ROOT / "scripts" / "frontend_query_params_allow.txt"
AXIOS_PATH = ROOT / "frontend" / "src" / "api" / "axios.js"
MOUNT = "api/django"

# Paramètres acceptés sur toute vue DRF (miroir de PARAMETRES_PLATEFORME de
# core/parametres_requete.py — DRF honore ?format= partout).
PARAMETRES_PLATEFORME = frozenset({"format"})

PROFONDEUR_MAX = 10

# Enveloppes de bibliothèque : ``const NOM = H(..., fn)`` rend une fonction qui
# reçoit les arguments de ses appelants (valeur = index de ``fn`` dans H).
ENVELOPPES = {"createAsyncThunk": 1, "useCallback": 0}
# Appelants qui invoquent la fonction passée SANS argument (aucun paramètre).
SANS_ARGUMENT = frozenset({"useEffect", "useLayoutEffect", "setTimeout", "setInterval",
                           "requestAnimationFrame", "queueMicrotask"})
# Fonctions dont les appels HTTP internes sont modélisés à part (fabrique CRUD).
MODELISEES = frozenset({"makeResourceFactory"})
HOOKS_DEPENDANCES = frozenset({"useEffect", "useLayoutEffect", "useCallback", "useMemo"})
PLACEHOLDER = "{}"

HTTP_URL_CONFIG = {"get": 1, "delete": 1, "head": 1, "options": 1,
                   "post": 2, "put": 2, "patch": 2}
CLIENT_HINT = FrontendCalls.CLIENT_HINT
DECLARATION = re.compile(r"parametres-requete\s*:\s*([\w\s,.\[\]-]*)")
CHEMINS_DECLARES = re.compile(r"chemins-requete\s*:\s*([\w\s/{}.-]*)")
IDENT = re.compile(r"^[A-Za-z_$][\w$]*$")
MOTS_CLES = frozenset({
    "if", "for", "while", "switch", "catch", "function", "return", "typeof",
    "await", "new", "import", "export", "else", "do", "try", "with", "super",
    "constructor", "yield", "delete", "void", "in", "of", "instanceof", "case",
})


# ===========================================================================
# 1. Contrat : opérations + paramètres déclarés (instantané versionné)
# ===========================================================================

def _segments_gabarit(chemin: str) -> tuple:
    return tuple(PLACEHOLDER if s.startswith("{") else s
                 for s in chemin.split("/") if s)


def charger_contrat(texte: str) -> dict:
    """{(methode, segments): frozenset(noms)} pour toute opération /api/django."""
    contrat = {}
    for ligne in texte.splitlines():
        if ligne.startswith("- ") and " -> " in ligne:
            tete = ligne[2:].split(" -> ", 1)[0].split(" ", 1)
            if len(tete) == 2 and tete[1].startswith(f"/{MOUNT}/"):
                contrat.setdefault((tete[0], _segments_gabarit(tete[1])), frozenset())
    _, _, reste = texte.partition("\nquery_params:\n")
    reste, _, _ = reste.partition("\ncomponents:\n")
    for ligne in reste.splitlines():
        if not ligne.startswith("  ") or ": " not in ligne:
            continue
        tete, _, noms = ligne.strip().partition(": ")
        methode, _, chemin = tete.partition(" ")
        if chemin.startswith(f"/{MOUNT}/"):
            contrat[(methode, _segments_gabarit(chemin))] = frozenset(noms.split())
    return contrat


class Contrat:
    def __init__(self, operations: dict):
        self.par_methode = {}
        for (methode, segs), noms in operations.items():
            self.par_methode.setdefault((methode, len(segs)), []).append((segs, noms))

    def autorises(self, methode: str, appel: tuple):
        """frozenset des noms déclarés, ou None si aucune opération ne correspond."""
        meilleurs, score_max = [], -1
        for segs, noms in self.par_methode.get((methode, len(appel)), ()):
            score = 0
            for a, b in zip(appel, segs):
                if a == b:
                    score += 2
                elif a == ANY and b == PLACEHOLDER:
                    score += 2
                elif a == ANY or b == PLACEHOLDER:
                    score += 1
                else:
                    break
            else:
                if score > score_max:
                    meilleurs, score_max = [noms], score
                elif score == score_max:
                    meilleurs.append(noms)
        if not meilleurs:
            return None
        return frozenset().union(*meilleurs)


# ===========================================================================
# 2. Lexique : un module JS (code sans commentaires, masque, têtes de fonction)
# ===========================================================================

OUVRANTS, FERMANTS = "([{", ")]}"


def _apparier(masked: str, i: int) -> int:
    """Index du crochet fermant celui ouvert en ``i`` (ou len)."""
    prof = 0
    for j in range(i, len(masked)):
        c = masked[j]
        if c in OUVRANTS:
            prof += 1
        elif c in FERMANTS:
            prof -= 1
            if prof == 0:
                return j
    return len(masked)


def _apparier_arriere(masked: str, j: int) -> int:
    prof = 0
    for i in range(j, -1, -1):
        c = masked[i]
        if c in FERMANTS:
            prof += 1
        elif c in OUVRANTS:
            prof -= 1
            if prof == 0:
                return i
    return -1


def _decouper(masked: str, s: int, e: int, sep: str = ",") -> list:
    """Segments (debut, fin) séparés par ``sep`` au niveau 0 dans [s, e)."""
    morceaux, prof, debut = [], 0, s
    for i in range(s, e):
        c = masked[i]
        if c in OUVRANTS:
            prof += 1
        elif c in FERMANTS:
            prof -= 1
        elif c == sep and prof == 0:
            morceaux.append((debut, i))
            debut = i + 1
    morceaux.append((debut, e))
    return [_rogner(masked, a, b) for a, b in morceaux if masked[a:b].strip()]


def _rogner(texte: str, s: int, e: int):
    while s < e and texte[s].isspace():
        s += 1
    while e > s and texte[e - 1].isspace():
        e -= 1
    return s, e


def _fin_expression(masked: str, s: int) -> int:
    """Fin d'une expression commençant en ``s`` (corps d'arrow, initialiseur)."""
    prof, n = 0, len(masked)
    i = s
    while i < n:
        c = masked[i]
        if c in OUVRANTS:
            prof += 1
        elif c in FERMANTS:
            if prof == 0:
                return i
            prof -= 1
        elif prof == 0 and c in ",;":
            return i
        elif prof == 0 and c == "\n":
            avant = masked[s:i].rstrip()
            j = i
            while j < n and masked[j].isspace():
                j += 1
            suivant = masked[j] if j < n else ""
            if avant and avant[-1] not in "=([{,?:|&+-*/<>!" and suivant not in ".?:|&+-*/=,)]}":
                return i
        i += 1
    return n


class Tete:
    """Une fonction : nom, paramètres (index -> (nom, champ)), corps."""

    __slots__ = ("debut", "nom", "params", "corps_debut", "corps_fin", "fin")

    def __init__(self, debut, nom, params, corps_debut, corps_fin, bloc=True):
        self.debut, self.nom, self.params = debut, nom, params
        self.corps_debut, self.corps_fin = corps_debut, corps_fin
        # fin (exclusive) de l'expression de fonction entière
        self.fin = corps_fin + 1 if bloc else corps_fin

    def position_de(self, ident):
        """(index, champ) du paramètre ``ident`` ou None."""
        for index, nom, champ in self.params:
            if nom == ident:
                return index, champ
        return None


def _params_de(masked: str, code: str, s: int, e: int) -> list:
    """[(index, nom, champ)] — ``champ`` non nul pour un paramètre destructuré."""
    sortie = []
    for index, (a, b) in enumerate(_decouper(masked, s, e)):
        texte = code[a:b]
        if texte.startswith("..."):
            continue
        if texte.startswith("{"):
            fin = _apparier(masked, a)
            for c, d in _decouper(masked, a + 1, fin):
                prop = code[c:d].split("=", 1)[0].strip()
                if ":" in prop:
                    champ, _, nom = prop.partition(":")
                    sortie.append((index, nom.strip(), champ.strip()))
                elif IDENT.match(prop):
                    sortie.append((index, prop, prop))
            continue
        nom = texte.split("=", 1)[0].strip()
        if IDENT.match(nom):
            sortie.append((index, nom, None))
    return sortie


_NOM_AVANT = re.compile(r"([A-Za-z_$][\w$]*)\s*[:=]\s*(?:async\s*)?$")
# `const charger = useCallback((p) => …)` : la fonction porte le nom affecté.
_NOM_CALLBACK = re.compile(r"([A-Za-z_$][\w$]*)\s*=\s*useCallback\s*\(\s*(?:async\s*)?$")
_FUNCTION = re.compile(r"\bfunction\b\s*\*?\s*([A-Za-z_$][\w$]*)?\s*\(")
_METHODE = re.compile(r"(?<![\w$.])(?:async\s+)?([A-Za-z_$][\w$]*)\s*\(")


def _tetes(code: str, masked: str) -> list:
    return (_tetes_fleches(code, masked) + _tetes_function(code, masked)
            + _tetes_methodes(code, masked))


def _tetes_fleches(code: str, masked: str) -> list:
    tetes = []
    # a) arrows
    for m in re.finditer(r"=>", masked):
        k = m.start() - 1
        while k >= 0 and masked[k].isspace():
            k -= 1
        if k < 0:
            continue
        if masked[k] == ")":
            ouvre = _apparier_arriere(masked, k)
            if ouvre < 0:
                continue
            params = _params_de(masked, code, ouvre + 1, k)
            avant = masked[max(0, ouvre - 80):ouvre]
        elif re.match(r"[\w$]", masked[k]):
            d = k
            while d > 0 and re.match(r"[\w$]", masked[d - 1]):
                d -= 1
            ouvre = d
            params = [(0, masked[d:k + 1], None)]
            avant = masked[max(0, d - 80):d]
        else:
            continue
        nm = _NOM_AVANT.search(avant) or _NOM_CALLBACK.search(avant)
        nom = nm.group(1) if nm else None
        c = m.end()
        while c < len(masked) and masked[c].isspace():
            c += 1
        bloc = c < len(masked) and masked[c] == "{"
        fin = _apparier(masked, c) if bloc else _fin_expression(masked, c)
        tetes.append(Tete(ouvre, nom, params, c, fin, bloc))
    return tetes


def _tetes_function(code: str, masked: str) -> list:
    tetes = []
    # b) function nom(...) { }
    for m in _FUNCTION.finditer(masked):
        ouvre = m.end() - 1
        ferme = _apparier(masked, ouvre)
        c = ferme + 1
        while c < len(masked) and masked[c].isspace():
            c += 1
        if c >= len(masked) or masked[c] != "{":
            continue
        nom = m.group(1)
        if not nom:
            nm = _NOM_AVANT.search(masked[max(0, m.start() - 80):m.start()])
            nom = nm.group(1) if nm else None
        tetes.append(Tete(m.start(), nom, _params_de(masked, code, ouvre + 1, ferme),
                          c, _apparier(masked, c)))
    return tetes


def _tetes_methodes(code: str, masked: str) -> list:
    tetes = []
    # c) méthode raccourcie  nom(...) { }
    for m in _METHODE.finditer(masked):
        nom = m.group(1)
        if nom in MOTS_CLES:
            continue
        ouvre = m.end() - 1
        ferme = _apparier(masked, ouvre)
        c = ferme + 1
        while c < len(masked) and masked[c] in " \t":
            c += 1
        if c >= len(masked) or masked[c] != "{":
            continue
        k = m.start() - 1
        while k >= 0 and masked[k].isspace():
            k -= 1
        if k >= 0 and masked[k] not in "{,;}":
            continue
        tetes.append(Tete(m.start(), nom, _params_de(masked, code, ouvre + 1, ferme),
                          c, _apparier(masked, c)))
    return tetes


_IMPORT = re.compile(r"""(?:\bfrom\s*|\bimport\s*\(\s*|\bimport\s+)(['"])([^'"]+)\1""")


_REGEX_AVANT = re.compile(r"[(,=:\[!&|?{};+\-*%~^<>]\s*$")
_REGEX_MOT = re.compile(r"\b(return|typeof|instanceof|in|of|new|delete|void|case|do|else|yield|await)\s*$")


def _commentaire(src: str, out: list, masked: list, i: int):
    """Efface le commentaire ouvert en ``i`` ; index suivant (None si ``i`` n'en ouvre pas)."""
    n = len(src)
    two = src[i:i + 2]
    if two == "//":
        j = src.find("\n", i)
        j = n if j < 0 else j
        for k in range(i, j):
            out[k] = masked[k] = " "
        return j
    if two == "/*":
        j = src.find("*/", i + 2)
        j = n if j < 0 else j + 2
        for k in range(i, j):
            if src[k] != "\n":
                out[k] = masked[k] = " "
        return j
    return None


def _fin_chaine(src: str, i: int, c: str) -> int:
    """Index (exclu) de la fin de la chaîne ouverte en ``i`` par ``c``."""
    n = len(src)
    j = i + 1
    while j < n:
        if src[j] == "\\":
            j += 2
            continue
        if src[j] == c or (c != "`" and src[j] == "\n"):
            break
        j += 1
    return min(j + 1, n)


def _fin_regex(src: str, i: int):
    """Index du ``/`` fermant le littéral regex ouvert en ``i`` (None s'il n'y en a pas)."""
    n = len(src)
    j = i + 1
    in_class = False
    while j < n and src[j] != "\n":
        if src[j] == "\\":
            j += 2
            continue
        if src[j] == "[":
            in_class = True
        elif src[j] == "]":
            in_class = False
        elif src[j] == "/" and not in_class:
            break
        j += 1
    return j if j < n and src[j] == "/" else None


def scanner_js(src: str):
    """Variante du lexeur de ``check_api_contract.scan_js`` (même sortie :
    code sans commentaires, jetons de chaîne, code masqué) qui tient compte du
    TEXTE JSX : une apostrophe ou un guillemet collé à une lettre
    (``l'automatisation``, ``d'un``) n'ouvre jamais une chaîne JS — ``x'…'``
    est invalide en JavaScript. Sans cela, une seule apostrophe de texte JSX
    masquait tout le fichier jusqu'à l'apostrophe suivante, et les appels
    qu'il contenait devenaient invisibles."""
    out = list(src)
    masked = list(src)
    tokens = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        suivant = _commentaire(src, out, masked, i)
        if suivant is not None:
            i = suivant
            continue
        if c in "'\"" and i > 0 and (src[i - 1].isalnum() or src[i - 1] in "’"):
            i += 1  # apostrophe de texte JSX
            continue
        if c in "'\"`":
            end = _fin_chaine(src, i, c)
            tokens.append((i, end, c, src[i + 1:end - 1]))
            for k in range(i + 1, end - 1):
                if src[k] != "\n":
                    masked[k] = " "
            i = end
            continue
        if c == "/":
            before = src[max(0, i - 40):i]
            if _REGEX_AVANT.search(before) or _REGEX_MOT.search(before) or not before.strip():
                j = _fin_regex(src, i)
                if j is not None:
                    for k in range(i + 1, j):
                        masked[k] = " "
                    i = j + 1
                    continue
        i += 1
    return "".join(out), tokens, "".join(masked)


_EXTENSIONS = ("", ".js", ".jsx", ".mjs", "/index.js", "/index.jsx")


def _resoudre_import(path: Path, spec: str):
    """Chemin relatif au dépôt du module importé (imports relatifs seulement)."""
    if not spec.startswith("."):
        return None
    base = os.path.normpath(os.path.join(str(path.parent), spec))
    for ext in _EXTENSIONS:
        cand = base + ext
        if os.path.isfile(cand):
            try:
                return Path(cand).relative_to(ROOT).as_posix()
            except ValueError:
                return Path(cand).as_posix()
    return None


class Module:
    def __init__(self, path: Path, src: str):
        self.path = path
        try:
            self.rel = path.relative_to(ROOT).as_posix()
        except ValueError:
            self.rel = path.as_posix()
        self.src = src
        self.code, tokens, self.masked = scanner_js(src)
        self.tokens = tokens
        self.token_at = {d: (f, q, raw) for d, f, q, raw in tokens}
        self.consts = FrontendCalls([])._constants(self.code, self.token_at, tokens, self.masked)
        self.tetes = _tetes(self.code, self.masked)
        self.stem = path.stem
        self.imports = {r for r in (_resoudre_import(path, m.group(2))
                                    for m in _IMPORT.finditer(src)) if r}
        self.lignes = src.split("\n")
        self._enclos = None

    def ligne(self, pos: int) -> int:
        return self.code.count("\n", 0, pos) + 1

    def declaration(self, pos: int):
        """Noms déclarés par commentaire ``parametres-requete:`` sur la ligne de
        ``pos`` ou l'une des deux lignes au-dessus, sinon None."""
        n = self.ligne(pos)
        for k in (n, n - 1, n - 2):
            if 1 <= k <= len(self.lignes):
                m = DECLARATION.search(self.lignes[k - 1])
                if m and ("//" in self.lignes[k - 1] or "/*" in self.lignes[k - 1]):
                    return [x for x in re.split(r"[\s,]+", m.group(1)) if x]
        return None

    def chemins_declares(self, pos: int):
        """Gabarits ``chemins-requete: /a/{id}/b/ /c/`` déclarés en commentaire
        sur la ligne de ``pos`` ou l'une des trois lignes au-dessus."""
        n = self.ligne(pos)
        for k in (n, n - 1, n - 2, n - 3):
            if 1 <= k <= len(self.lignes):
                ligne = self.lignes[k - 1]
                m = CHEMINS_DECLARES.search(ligne)
                if m and ("//" in ligne or "/*" in ligne):
                    return [x for x in m.group(1).split() if x.startswith("/")]
        return []

    def enclos(self, pos: int) -> int:
        """Index du crochet ouvrant le plus interne qui contient ``pos`` (-1)."""
        if self._enclos is None:
            tab, pile = [], []
            for c in self.masked:
                tab.append(pile[-1] if pile else -1)
                if c in OUVRANTS:
                    pile.append(len(tab) - 1)
                elif c in FERMANTS and pile:
                    pile.pop()
            self._enclos = tab
        if 0 <= pos < len(self._enclos):
            return self._enclos[pos]
        return -1

    def chemin_objet(self, tete):
        """(genre, chaîne de clés parentes, racine) d'une fonction nommée.

        genre ``prop`` : propriété d'un objet littéral (``getRules: (p) =>``,
        méthode raccourcie) ; ``fonction`` : déclaration de module ;
        ``locale`` : déclaration dans un corps de fonction."""
        m = self.masked
        avant = m[max(0, tete.debut - 120):tete.debut]
        est_prop = (m[tete.debut:tete.debut + len(tete.nom)] == tete.nom
                    and not avant.rstrip().endswith("function")) or re.search(
            r"(?<![\w$])%s\s*:\s*(?:async\s*)?(?:function\b[^(]*)?$" % re.escape(tete.nom), avant)
        if not est_prop:
            debut = tete.debut
            dm = re.search(r"(?:const|let|var)\s+%s\s*=\s*(?:async\s*)?"
                           r"(?:function\b[^(]*|useCallback\s*\(\s*(?:async\s*)?)?$"
                           % re.escape(tete.nom), avant)
            if dm:
                debut = tete.debut - len(avant) + dm.start()
            ouvrant = self.enclos(debut)
            return ("fonction" if ouvrant < 0 else "locale"), [], None
        chaine, racine = [], None
        pos = tete.debut
        while True:
            b = self.enclos(pos)
            if b < 0 or m[b] != "{":
                break
            av = m[max(0, b - 120):b]
            km = re.search(r"([A-Za-z_$][\w$]*)\s*:\s*$", av)
            if km:
                chaine.insert(0, km.group(1))
                pos = b
                continue
            rm = re.search(r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*$", av)
            if rm:
                racine = rm.group(1)
            elif re.search(r"export\s+default\s*$", av):
                racine = self.stem
            break
        return "prop", chaine, racine

    def tetes_contenant(self, pos: int):
        return sorted((t for t in self.tetes if t.corps_debut <= pos <= t.corps_fin),
                      key=lambda t: t.corps_debut, reverse=True)


# ===========================================================================
# 3. Résolution des noms de paramètres
# ===========================================================================

class Resultat:
    """Noms trouvés (nom -> origines) + expressions non résolues."""

    def __init__(self):
        self.noms = {}
        self.non_resolus = []

    def nom(self, nom, origine):
        self.noms.setdefault(nom, set()).add(origine)

    def inconnu(self, origine, raison):
        self.non_resolus.append((origine, raison))

    def fusion(self, autre):
        for nom, origines in autre.noms.items():
            self.noms.setdefault(nom, set()).update(origines)
        self.non_resolus.extend(autre.non_resolus)
        return self


_MUTATION_POINT = r"\b{n}\s*\.\s*([A-Za-z_$][\w$]*)\s*=(?!=)"
_MUTATION_SET = r"\b{n}\s*\.\s*(?:set|append)\s*\(\s*"
_ASSIGN = r"\bObject\.assign\s*\(\s*{n}\s*,"


class Analyse:
    def __init__(self, modules: list, entite: list):
        self.modules = modules
        self.entite = entite
        self.importeurs = {}
        for mod in modules:
            for cible in mod.imports:
                self.importeurs.setdefault(cible, []).append(mod)
        self.passe_plats = set()
        self.orphelins = set()
        self.cache_sites = {}
        # liaisons (module, tête, paramètre) -> (module, debut, fin, env, champ)
        self.env = {}
        # index global des accès pointés `qual.nom` (un seul balayage)
        self.pointes = {}
        for mod in modules:
            # anticipation : `a.b.c` donne `a.b` ET `b.c` (accès chaînés)
            for m in re.finditer(r"(?<![\w$])(?=([A-Za-z_$][\w$]*)\s*\??\.\s*([A-Za-z_$][\w$]*)\b)",
                                 mod.masked):
                self.pointes.setdefault(m.group(2), []).append((mod, m))

    def _modules_clients(self, mod):
        """Le module, ceux qui l'importent, et (2e saut) ceux qui importent un
        module ``*Api`` qui l'importe (fragments étalés dans un client API)."""
        vus = {id(mod): mod}
        premier = self.importeurs.get(mod.rel, [])
        for m in premier:
            vus.setdefault(id(m), m)
        for m in premier:
            if m.stem.lower().endswith("api") or m.stem == "index":
                for m2 in self.importeurs.get(m.rel, []):
                    vus.setdefault(id(m2), m2)
        return list(vus.values())

    def _cadre_sites(self, mod, tete, genre_force):
        """(genre, chaîne, racine, modules, motif) de la recherche des appelants de ``tete``."""
        nom = re.escape(tete.nom)
        if genre_force:
            genre, chaine, racine = genre_force, [], None
        else:
            genre, chaine, racine = mod.chemin_objet(tete)
        if genre == "locale":
            modules = [mod]
            motif = r"(?<![\w$.])()(%s)\b" % nom
        elif genre == "fonction":
            modules = self._modules_clients(mod)
            motif = r"(?<![\w$])()(%s)\b" % nom
        elif chaine:
            modules = self.modules
            motif = r"(?<![\w$])(%s)\s*\??\.\s*(%s)\b" % (re.escape(chaine[-1]), nom)
        else:
            modules = self._modules_clients(mod)
            motif = r"([A-Za-z_$][\w$]*)\s*\??\.\s*(%s)\b" % nom
        return genre, chaine, racine, modules, motif

    @staticmethod
    def _alias_fragments(modules, racine):
        """Clés sous lesquelles ``racine`` est étalé : `calepinages: { ...projet }` → `x.calepinages.f(`."""
        alias = set()
        for cmod in modules:
            for sm in re.finditer(r"\.\.\.\s*%s\b" % re.escape(racine), cmod.masked):
                b = cmod.enclos(sm.start())
                km = re.search(r"([A-Za-z_$][\w$]*)\s*:\s*$", cmod.masked[max(0, b - 80):max(0, b)])
                if b >= 0 and cmod.masked[b] == "{" and km:
                    alias.add(km.group(1))
        return alias

    def _occurrences_sites(self, tete, genre, chaine, modules, motif):
        """[(module, correspondance)] des mentions du nom de ``tete`` dans ``modules``."""
        if genre == "prop":
            ids = {id(x) for x in modules}
            return [(cmod, m) for cmod, m in self.pointes.get(tete.nom, ())
                    if id(cmod) in ids and (not chaine or m.group(1) == chaine[-1])]
        return [(cmod, m) for cmod in modules for m in re.finditer(motif, cmod.masked)]

    def sites(self, mod, tete, genre_force=None):
        """(appels, références) de la fonction ``tete`` : [(module, pos)].

        Les appelants sont QUALIFIÉS pour ne pas confondre deux fonctions de
        même nom : ``parent.nom(`` pour une méthode imbriquée
        (``instagram.media``), ``<client>Api.nom(`` restreint aux modules qui
        importent le client pour une méthode de premier niveau, ``nom(`` dans
        les importeurs pour une fonction exportée, la portée locale sinon."""
        cle = (mod.rel, tete.debut)
        if cle in self.cache_sites:
            return self.cache_sites[cle]
        genre, chaine, racine, modules, motif = self._cadre_sites(mod, tete, genre_force)
        appels, refs = [], []
        alias = {racine} if racine else set()
        if genre == "prop" and not chaine and racine:
            alias |= self._alias_fragments(modules, racine)
        occurrences = self._occurrences_sites(tete, genre, chaine, modules, motif)
        for cmod, m in occurrences:
            if genre == "prop" and not chaine:
                qual = m.group(1)
                if qual not in alias and not qual.lower().endswith("api"):
                    continue
            debut_nom = m.start(2)
            if cmod is mod and tete.debut <= debut_nom < tete.corps_debut:
                continue  # la définition elle-même
            suite = cmod.masked[m.end(2):m.end(2) + 40]
            appel = re.match(r"\s*(?:\?\.)?\s*\(", suite)
            if appel:
                appels.append((cmod, m.end(2) + appel.end() - 1))
                continue
            if re.match(r"\s*(?::|=(?![=>]))", suite):
                continue  # définition / affectation
            debut_ligne = cmod.code.rfind("\n", 0, debut_nom) + 1
            fin_ligne = cmod.code.find("\n", debut_nom)
            ligne = cmod.code[debut_ligne:fin_ligne if fin_ligne >= 0 else None]
            if re.match(r"\s*(import|export)\b", ligne) or "} from" in ligne:
                continue
            if cmod is mod and any(t.debut == debut_nom for t in mod.tetes):
                continue
            refs.append((cmod, debut_nom))
        self.cache_sites[cle] = (appels, refs)
        return appels, refs

    def gabarit_fonction(self, mod, nom):
        """Chemin rendu par ``nom`` (fonction locale ou importée dont le corps
        est un seul gabarit : ``pivot = (id) => `/calepinage/calepinages/${id}/```),
        ses paramètres devenant des segments dynamiques ; None sinon."""
        cibles = [(mod, t) for t in mod.tetes if t.nom == nom]
        if not cibles:
            for hmod in self.modules:
                if hmod.rel in mod.imports:
                    cibles += [(hmod, t) for t in hmod.tetes if t.nom == nom]
        for hmod, ht in cibles:
            for a, b in self._retours(hmod, ht):
                a, b = _rogner(hmod.code, a, b)
                if a in hmod.token_at and hmod.token_at[a][0] >= b:
                    _, quote, raw = hmod.token_at[a]
                    valeur = resolve_template(raw, quote, hmod.consts)
                    if isinstance(valeur, str) and valeur.startswith("/"):
                        return valeur
        return None

    # -- origine lisible ----------------------------------------------------
    @staticmethod
    def ori(mod, pos):
        return f"{mod.rel}:{mod.ligne(pos)}"

    # -- expression -> noms --------------------------------------------------
    def _ref_react(self, mod, texte, decl, res, mode, prof, vus):
        """``R.current`` : `const R = useRef(init)` + `R.current = expr` (None si non applicable)."""
        rm = re.fullmatch(r"([A-Za-z_$][\w$]*)\.current", texte)
        if not rm or decl is not None:
            return None
        n = re.escape(rm.group(1))
        sources = [x for x in re.finditer(r"\b(?:const|let|var)\s+%s\s*=\s*useRef\s*\(" % n,
                                          mod.masked)]
        if not sources:
            return None
        for x in sources:
            ouvre = x.end() - 1
            for a, b in _decouper(mod.masked, ouvre + 1, _apparier(mod.masked, ouvre))[:1]:
                res.fusion(self.cles(mod, a, b, mode, prof, vus))
        for x in re.finditer(r"(?<![\w$.])%s\.current\s*=(?![=>])" % n, mod.masked):
            res.fusion(self.cles(mod, x.end(), _fin_expression(mod.masked, x.end()),
                                 mode, prof, vus))
        return res

    def cles(self, mod, s, e, mode, prof, vus=frozenset()):
        """Noms de paramètres portés par l'expression [s, e).

        mode 'params' : l'expression EST l'objet params ;
        mode 'config' : l'expression est une config axios (on lit ``.params``).
        """
        res = Resultat()
        s, e = _rogner(mod.code, s, e)
        texte = mod.code[s:e]
        if not texte or texte in ("undefined", "null", "{}", "''", '""', "false"):
            return res
        decl = mod.declaration(s)
        if prof > PROFONDEUR_MAX:
            return self._inconnu(mod, s, "profondeur de passe-plat dépassée", res, mode, decl)
        # parenthèses englobantes
        if mod.masked[s] == "(" and _apparier(mod.masked, s) == e - 1:
            return self.cles(mod, s + 1, e - 1, mode, prof, vus)
        if texte.startswith("await "):
            return self.cles(mod, s + 6, e, mode, prof, vus)
        # ternaire / logiques au niveau 0
        branches = self._ternaire(mod, s, e)
        if branches:
            for a, b in branches:
                res.fusion(self.cles(mod, a, b, mode, prof, vus))
            return res
        for op in ("||", "??"):
            parts = self._binaire(mod, s, e, op)
            if parts:
                for a, b in parts:
                    res.fusion(self.cles(mod, a, b, mode, prof, vus))
                return res
        parts = self._binaire(mod, s, e, "&&")
        if parts:
            return self.cles(mod, parts[-1][0], parts[-1][1], mode, prof, vus)
        # objet littéral
        if mod.masked[s] == "{" and _apparier(mod.masked, s) == e - 1:
            return self._objet(mod, s, e, mode, prof, vus)
        # new URLSearchParams(x)
        m = re.match(r"new\s+URLSearchParams\s*\(", texte)
        if m and mode == "params":
            ouvre = s + m.end() - 1
            ferme = _apparier(mod.masked, ouvre)
            if ferme == e - 1 or mod.code[ferme + 1:e].strip() in (".toString()", ""):
                return self.cles(mod, ouvre + 1, ferme, "params", prof, vus)
        if texte.endswith(".toString()") and mode == "params":
            return self.cles(mod, s, e - len(".toString()"), mode, prof, vus)
        # chaîne littérale « a=1&b=2 » (init d'URLSearchParams)
        if s in mod.token_at and mod.token_at[s][0] >= e and mode == "params":
            _, quote, raw = mod.token_at[s]
            for nom in _noms_chaine_requete(raw, quote):
                res.nom(nom, self.ori(mod, s))
            return res
        if IDENT.match(texte):
            return self._identifiant(mod, texte, s, mode, prof, vus, decl)
        retour = self._ref_react(mod, texte, decl, res, mode, prof, vus)
        if retour is not None:
            return retour
        cm = re.match(r"([A-Za-z_$][\w$]*)\s*\(", texte)
        if cm and decl is None and _apparier(mod.masked, s + cm.end() - 1) == e - 1:
            retour = self._retour_appel(mod, cm.group(1), s + cm.end() - 1, mode, prof, vus)
            if retour is not None:
                return retour
        return self._inconnu(mod, s, f"expression non résolue « {_court(texte)} »", res, mode, decl)

    @staticmethod
    def _retours(hmod, ht):
        """Spans des expressions RENDUES par la fonction ``ht`` (corps
        d'expression, ou chaque ``return`` de son propre niveau)."""
        if hmod.masked[ht.corps_debut:ht.corps_debut + 1] != "{":
            return [(ht.corps_debut, ht.corps_fin)]
        spans = []
        corps = hmod.masked[ht.corps_debut:ht.corps_fin]
        for occ in re.finditer(r"\breturn\b", corps):
            pos = ht.corps_debut + occ.start()
            interne = hmod.tetes_contenant(pos)
            if interne and interne[0] is not ht:
                continue
            debut = pos + len("return")
            spans.append((debut, _fin_expression(hmod.masked, debut)))
        return spans

    def _retour_appel(self, mod, nom, ouvre, mode, prof, vus):
        """Noms portés par ce que RENVOIE l'appel ``nom(...)`` : fonction du
        frontend (locale ou importée) dont on lit les ``return`` en liant ses
        paramètres aux arguments de ce site ; ``useMemo(() => …)`` lit sa
        fabrique. None si la fonction n'est pas trouvée."""
        args = _decouper(mod.masked, ouvre + 1, _apparier(mod.masked, ouvre))
        if nom == "useMemo":
            if not args:
                return None
            a = args[0][0]
            cibles = [(mod, t) for t in mod.tetes if a <= t.debut <= a + 6 and t.fin <= args[0][1]]
            liaisons = False
        else:
            cibles = [(mod, t) for t in mod.tetes if t.nom == nom and t.debut < ouvre]
            if not cibles:
                for hmod in self.modules:
                    if hmod.rel in mod.imports:
                        cibles += [(hmod, t) for t in hmod.tetes if t.nom == nom
                                   and hmod.chemin_objet(t)[0] == "fonction"]
            liaisons = True
        if not cibles:
            return None
        res = Resultat()
        for hmod, ht in cibles:
            env = dict(self.env)
            if liaisons:
                for idx, pnom, pch in ht.params:
                    env[(hmod.rel, ht.debut, pnom)] = (
                        (mod,) + args[idx] + (self.env, pch) if idx < len(args) else None)
            sauve, self.env = self.env, env
            try:
                for a, b in self._retours(hmod, ht):
                    res.fusion(self.cles(hmod, a, b, mode, prof + 1, vus))
            finally:
                self.env = sauve
        return res

    def _inconnu(self, mod, s, raison, res, mode, decl):
        if decl is not None:
            if mode == "params":
                for nom in decl:
                    res.nom(nom, self.ori(mod, s) + " (déclaré)")
                return res
            for nom in decl:
                res.nom(nom, self.ori(mod, s) + " (déclaré)")
            return res
        res.inconnu(self.ori(mod, s), raison)
        return res

    def _ternaire(self, mod, s, e):
        m = mod.masked
        prof, q = 0, None
        i = s
        while i < e:
            c = m[i]
            if c in OUVRANTS:
                prof += 1
            elif c in FERMANTS:
                prof -= 1
            elif prof == 0 and c == "?":
                if m[i + 1:i + 2] in ("?", ".") or m[i - 1:i] == "?":
                    i += 2
                    continue
                q = i
                break
            i += 1
        if q is None:
            return None
        prof, imbrique = 0, 0
        for j in range(q + 1, e):
            c = m[j]
            if c in OUVRANTS:
                prof += 1
            elif c in FERMANTS:
                prof -= 1
            elif prof == 0 and c == "?" and m[j + 1:j + 2] not in ("?", ".") and m[j - 1:j] != "?":
                imbrique += 1
            elif prof == 0 and c == ":":
                if imbrique == 0:
                    return [(q + 1, j), (j + 1, e)]
                imbrique -= 1
        return None

    def _binaire(self, mod, s, e, op):
        m = mod.masked
        prof, coupes, i = 0, [], s
        while i < e - 1:
            c = m[i]
            if c in OUVRANTS:
                prof += 1
            elif c in FERMANTS:
                prof -= 1
            elif prof == 0 and m[i:i + 2] == op:
                coupes.append(i)
                i += 2
                continue
            i += 1
        if not coupes:
            return None
        bornes, debut = [], s
        for c in coupes:
            bornes.append((debut, c))
            debut = c + len(op)
        bornes.append((debut, e))
        return bornes

    def _objet(self, mod, s, e, mode, prof, vus):
        res = Resultat()
        for a, b in _decouper(mod.masked, s + 1, e - 1):
            texte = mod.code[a:b]
            if texte.startswith("..."):
                res.fusion(self.cles(mod, a + 3, b, mode, prof, vus))
                continue
            cle, valeur = None, None
            if texte.startswith("["):
                fin = _apparier(mod.masked, a)
                interne = mod.code[a + 1:fin].strip()
                valeur_cle = mod.consts.get(interne)
                if mode == "params":
                    if isinstance(valeur_cle, str):
                        res.nom(valeur_cle, self.ori(mod, a))
                    else:
                        decl = mod.declaration(a)
                        self._inconnu(mod, a, f"clé calculée « [{_court(interne)}] »", res, mode, decl)
                continue
            if a in mod.token_at:
                fin, _, raw = mod.token_at[a]
                reste = mod.code[fin:b].lstrip()
                if reste.startswith(":"):
                    cle = raw
                    valeur = (fin + len(mod.code[fin:b]) - len(reste) + 1, b)
            if cle is None:
                mm = re.match(r"(?:async\s+)?([A-Za-z_$][\w$]*)\s*(:|\()?", texte)
                if not mm:
                    continue
                if mm.group(2) == "(":
                    continue  # méthode
                cle = mm.group(1)
                if mm.group(2) == ":":
                    valeur = (a + mm.end(), b)
            if mode == "params":
                res.nom(cle, self.ori(mod, a))
            elif cle == "params":
                if valeur is None:
                    res.fusion(self._identifiant(mod, "params", a, "params", prof, vus,
                                                 mod.declaration(a)))
                else:
                    res.fusion(self.cles(mod, valeur[0], valeur[1], "params", prof, vus))
        return res

    def _identifiant(self, mod, nom, pos, mode, prof, vus, decl):
        res = Resultat()
        cle = (mod.rel, nom, pos, mode)
        if cle in vus:
            return res
        vus = vus | {cle}
        # déclaration locale la plus proche AVANT pos
        decl_pos = None
        for m in re.finditer(r"\b(?:const|let|var)\s+%s\s*=(?!=)" % re.escape(nom), mod.masked[:pos]):
            decl_pos = m
        # paramètre de la fonction englobante la plus interne
        tete, position = None, None
        for t in mod.tetes_contenant(pos):
            p = t.position_de(nom)
            if p is not None:
                tete, position = t, p
                break
        if decl_pos is not None and (tete is None or decl_pos.start() > tete.debut):
            debut = decl_pos.end()
            fin = _fin_expression(mod.masked, debut)
            res.fusion(self.cles(mod, debut, fin, mode, prof, vus))
            self._mutations(mod, nom, fin, pos, mode, res)
            return res
        if tete is not None and (mod.rel, tete.debut, nom) in self.env:
            # paramètre LIÉ (fonction d'ordre supérieur suivie depuis un site
            # précis) : on résout l'argument de CE site, pas tous les appelants.
            lien = self.env[(mod.rel, tete.debut, nom)]
            if lien is not None:
                bmod, a, b, benv, champ = lien
                sauve, self.env = self.env, benv
                try:
                    if champ is None:
                        res.fusion(self.cles(bmod, a, b, mode, prof + 1, vus))
                    else:
                        res.fusion(self._champ(bmod, a, b, champ, mode, prof + 1, vus))
                finally:
                    self.env = sauve
            self._mutations(mod, nom, tete.corps_debut, pos, mode, res)
            return res
        if tete is not None:
            res.fusion(self._passe_plat(mod, tete, position, mode, prof, vus, pos, decl))
            self._mutations(mod, nom, tete.corps_debut, pos, mode, res)
            return res
        const = mod.consts.get(nom)
        if isinstance(const, str) and mode == "params":
            for n in _noms_chaine_requete(const, "'"):
                res.nom(n, self.ori(mod, pos))
            return res
        return self._inconnu(mod, pos, f"identifiant « {nom} » non résolu", res, mode, decl)

    def _mutations(self, mod, nom, debut, fin, mode, res):
        if mode != "params":
            return
        zone = mod.masked[debut:fin]
        n = re.escape(nom)
        for m in re.finditer(_MUTATION_POINT.format(n=n), zone):
            res.nom(m.group(1), self.ori(mod, debut + m.start()))
        for m in re.finditer(r"(?<![\w$.])%s\s*\[" % n, zone):
            # p['x'] = … (clé littérale) / p[cle] = … (calculée)
            ouvre = debut + m.end() - 1
            ferme = _apparier(mod.masked, ouvre)
            if not re.match(r"\s*=(?![=>])", mod.masked[ferme + 1:ferme + 4]):
                continue
            interne_s, interne_e = _rogner(mod.code, ouvre + 1, ferme)
            if interne_s in mod.token_at and mod.token_at[interne_s][0] >= interne_e:
                res.nom(mod.token_at[interne_s][2], self.ori(mod, ouvre))
                continue
            interne = mod.code[interne_s:interne_e]
            if isinstance(mod.consts.get(interne), str):
                res.nom(mod.consts[interne], self.ori(mod, ouvre))
            else:
                self._inconnu(mod, ouvre, f"clé calculée « {nom}[{_court(interne)}] »",
                              res, mode, mod.declaration(ouvre))
        for m in re.finditer(_MUTATION_SET.format(n=n), zone):
            a = debut + m.end()
            if a in mod.token_at:
                res.nom(mod.token_at[a][2], self.ori(mod, a))
            else:
                self._inconnu(mod, a, f"clé calculée « {nom}.set(…) »", res, mode,
                              mod.declaration(a))
        for m in re.finditer(_ASSIGN.format(n=n), zone):
            ouvre = debut + zone.index("(", m.start())
            ferme = _apparier(mod.masked, ouvre)
            for a, b in _decouper(mod.masked, ouvre + 1, ferme)[1:]:
                res.fusion(self.cles(mod, a, b, "params", 0))

    # -- passe-plat : remonter aux appelants ---------------------------------
    def _passe_plat(self, mod, tete, position, mode, prof, vus, pos, decl):
        res = Resultat()
        index, champ = position
        if decl is not None:
            return self._inconnu(mod, pos, "", res, mode, decl)
        if not tete.nom:
            # fonction anonyme : elle est PASSÉE quelque part (argument d'une
            # fonction d'ordre supérieur, d'un createAsyncThunk, d'un useCallback)
            d = tete.debut
            am = re.search(r"async\s*$", mod.masked[max(0, d - 12):d])
            if am:
                d -= len(am.group(0))
            return self._passee(mod, d, tete.fin, "fonction anonyme", index, champ, mode,
                                prof + 1, vus)
        nom = tete.nom
        self.passe_plats.add((mod.rel, nom))
        appelants, references = self.sites(mod, tete)
        if not appelants and not references:
            self.orphelins.add((mod.rel, mod.ligne(tete.debut), nom) + tuple(
                map(str, mod.chemin_objet(tete))))
        res.fusion(self._depuis_appelants(appelants, nom, index, champ, mode, prof, vus))
        for rmod, rpos in references:
            m = rmod.masked
            d = rpos
            while d > 0 and (m[d - 1].isalnum() or m[d - 1] in "_$.?"):
                d -= 1
            if not self._est_passage(rmod, d, rpos + len(nom)):
                continue
            res.fusion(self._passee(rmod, d, rpos + len(nom), f"« {nom} »", index, champ, mode,
                                    prof + 1, vus))
        return res

    @staticmethod
    def _est_passage(mod, d, f):
        """Faux pour une simple LECTURE qui ne transmet pas la fonction :
        ``typeof x.f``, ``!x.f``, ``if (x.f)``, ``x.f.pending`` (membre)."""
        m = mod.masked
        if re.search(r"(?:\btypeof\s*|!\s*)$", m[max(0, d - 12):d]):
            return False
        if re.match(r"\s*\??\.\s*[A-Za-z_$]", m[f:f + 8]):
            return False
        b = mod.enclos(d)
        if b >= 0 and m[b] == "(":
            hm = re.search(r"([A-Za-z_$][\w$]*)\s*$", m[max(0, b - 20):b])
            if hm and hm.group(1) in ("if", "while") and not m[b + 1:d].strip():
                return False
        return True

    def _depuis_appelants(self, appelants, nom, index, champ, mode, prof, vus):
        res = Resultat()
        for cmod, ouvre in appelants:
            args = _decouper(cmod.masked, ouvre + 1, _apparier(cmod.masked, ouvre))
            if index >= len(args):
                continue
            a, b = args[index]
            if cmod.code[a:b].startswith("..."):
                self._inconnu(cmod, a, f"arguments étalés vers « {nom} »", res, mode,
                              cmod.declaration(a))
                continue
            if champ is None:
                res.fusion(self.cles(cmod, a, b, mode, prof + 1, vus))
            else:
                res.fusion(self._champ(cmod, a, b, champ, mode, prof + 1, vus))
        return res

    def _passee(self, rmod, d, f, libelle, index, champ, mode, prof, vus):
        """La fonction [d, f) est PASSÉE (sans être appelée) dans ``rmod``.

        Cas suivis : argument d'une fonction d'ordre supérieur du frontend
        (``toutesLesPages(gedApi.getX, { actif: 1 })``, ``{ appeler }`` passé à
        un hook) — on lit, dans le corps de cette fonction, l'appel du
        paramètre qui la reçoit en LIANT ses autres paramètres aux arguments
        de CE site ; enveloppe ``createAsyncThunk``/``useCallback`` affectée à
        un nom — on remonte aux appelants de ce nom. Sinon : NON RÉSOLU."""
        res = Resultat()
        raison = f"{libelle} passée par référence (paramètres invisibles)"
        if prof > PROFONDEUR_MAX:
            return self._inconnu(rmod, d, "profondeur de passe-plat dépassée", res, mode,
                                 rmod.declaration(d))
        m = rmod.masked
        b = rmod.enclos(d)
        cle_objet, debut_arg = None, d
        # alias : `const fn = api.metrics?.realLeads` puis `fn(…)`
        if re.search(r"(?:const|let|var)\s+[A-Za-z_$][\w$]*\s*=\s*$", m[max(0, d - 120):d]) \
                and not m[f:_fin_expression(m, d)].strip():
            return self._enveloppe(rmod, d, "alias", index, champ, mode, prof, vus, d)
        # prop JSX : `<Editeur loadFn={savApi.getX} />`
        if b >= 0 and m[b] == "{" and _apparier(m, b) == _rogner(m, f, len(m))[0]:
            am = re.search(r"([A-Za-z_$][\w$]*)\s*=\s*$", m[max(0, b - 80):b])
            if am and not m[b + 1:d].strip():
                return self._composant(rmod, b, am.group(1), libelle, d, index, champ, mode,
                                       prof, vus)
        if b >= 0 and m[b] == "{":
            cle_objet = self._cle_objet(rmod, b, d, f)
            if cle_objet is None:
                return self._inconnu(rmod, d, raison, res, mode, rmod.declaration(d))
            debut_arg = b
            b = rmod.enclos(b)
        if b >= 0 and m[b] == "[" and cle_objet is None:
            appel = rmod.enclos(b)
            hm = re.search(r"([A-Za-z_$][\w$]*)\s*$", m[max(0, appel - 80):max(0, appel)])
            if appel >= 0 and m[appel] == "(" and hm and hm.group(1) in HOOKS_DEPENDANCES:
                return res  # tableau de dépendances d'un hook : jamais appelée là
        if b < 0 or m[b] != "(":
            return self._inconnu(rmod, d, raison, res, mode, rmod.declaration(d))
        hm = re.search(r"([A-Za-z_$][\w$]*)\s*$", m[max(0, b - 80):b])
        if hm and hm.group(1) in SANS_ARGUMENT:
            return res
        if not hm or hm.group(1) in MOTS_CLES:
            return self._inconnu(rmod, d, raison, res, mode, rmod.declaration(d))
        nom_h = hm.group(1)
        args = _decouper(m, b + 1, _apparier(m, b))
        j = next((k for k, (x, y) in enumerate(args) if x <= debut_arg < y), None)
        if j is None or (cle_objet is None and args[j] != (d, f)):
            return self._inconnu(rmod, d, raison, res, mode, rmod.declaration(d))
        if cle_objet is None and ENVELOPPES.get(nom_h) == j:
            return self._enveloppe(rmod, b - len(m[max(0, b - 80):b]) + hm.start(), nom_h,
                                   index, champ, mode, prof, vus, d)
        candidats = self._candidats_hote(rmod, nom_h)
        if not candidats:
            return self._inconnu(rmod, d, raison + f" à « {nom_h} »", res, mode,
                                 rmod.declaration(d))
        for hmod, ht in candidats:
            param = self._param_recu(ht, j, cle_objet)
            if param is None:
                self._inconnu(rmod, d, raison + f" à « {nom_h} »", res, mode,
                              rmod.declaration(d))
                continue
            res.fusion(self._corps_lie(rmod, hmod, ht, args, param, index, champ, mode, prof, vus))
        return res

    @staticmethod
    def _cle_objet(rmod, b, d, f):
        """Clé de propriété sous laquelle la fonction [d, f) est rangée dans l'objet ouvert en ``b``."""
        m = rmod.masked
        prop = [(x, y) for x, y in _decouper(m, b + 1, _apparier(m, b)) if x <= d < y]
        if not prop:
            return None
        x, y = prop[0]
        km = re.match(r"([A-Za-z_$][\w$]*)\s*:\s*", rmod.code[x:y])
        if km and x + km.end() == d and y == f:
            return km.group(1)
        if x == d and y == f and IDENT.match(rmod.code[x:y]):
            return rmod.code[x:y]
        return None

    def _candidats_hote(self, rmod, nom_h):
        """[(module, tête)] des fonctions nommées ``nom_h`` : locales, sinon importées."""
        candidats = [(rmod, t) for t in rmod.tetes if t.nom == nom_h]
        if not candidats:
            for hmod in self.modules:
                if hmod.rel in rmod.imports:
                    candidats += [(hmod, t) for t in hmod.tetes if t.nom == nom_h
                                  and hmod.chemin_objet(t)[0] == "fonction"]
        return candidats

    @staticmethod
    def _param_recu(ht, j, cle_objet):
        """Nom du paramètre de ``ht`` qui reçoit la fonction passée (index ``j``, champ ``cle_objet``)."""
        param = None
        for idx, pnom, pch in ht.params:
            if idx == j and pch == cle_objet:
                param = pnom
        return param

    def _corps_lie(self, rmod, hmod, ht, args, param, index, champ, mode, prof, vus):
        """Corps de ``ht`` lu avec ses paramètres liés aux arguments ``args`` du site de ``rmod``."""
        env = dict(self.env)
        for idx, pnom, pch in ht.params:
            lien = (rmod,) + args[idx] + (self.env, pch) if idx < len(args) else None
            env[(hmod.rel, ht.debut, pnom)] = lien
        sauve, self.env = self.env, env
        try:
            return self._corps(hmod, ht, param, index, champ, mode, prof, vus)
        finally:
            self.env = sauve

    def _corps(self, hmod, ht, param, index, champ, mode, prof, vus):
        """Dans le corps de ``ht``, ce que reçoit le paramètre-fonction
        ``param`` : ses appels (argument ``index``) et ses re-passages."""
        res = Resultat()
        corps = hmod.masked[ht.corps_debut:ht.corps_fin]
        refs = set()
        for occ in re.finditer(r"(?<![\w$.])%s\b" % re.escape(param), corps):
            pos = ht.corps_debut + occ.start()
            suite = hmod.masked[pos + len(param):pos + len(param) + 20]
            appel = re.match(r"\s*(?:\?\.)?\s*\(", suite)
            avant = hmod.masked[max(0, pos - 80):pos]
            rm = re.search(r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*useRef\s*\(\s*$", avant) \
                or re.search(r"([A-Za-z_$][\w$]*)\.current\s*=\s*$", avant)
            if not appel and rm:
                refs.add(rm.group(1))  # rangée dans une ref React : suivre `R.current(…)`
                continue
            if not appel:
                if re.match(r"\s*(?:=(?![=>])|:)", suite) or not self._est_passage(
                        hmod, pos, pos + len(param)):
                    continue
                res.fusion(self._passee(hmod, pos, pos + len(param), f"« {param} »",
                                        index, champ, mode, prof + 1, vus))
                continue
            ouvre = pos + len(param) + appel.end() - 1
            res.fusion(self._depuis_appelants([(hmod, ouvre)], param, index, champ,
                                              mode, prof, vus))
        for ref in sorted(refs):
            for occ in re.finditer(r"(?<![\w$.])%s\.current\s*(?:\?\.)?\s*\(" % re.escape(ref), corps):
                ouvre = ht.corps_debut + occ.end() - 1
                res.fusion(self._depuis_appelants([(hmod, ouvre)], param, index, champ,
                                                  mode, prof, vus))
        return res

    def _composant(self, rmod, b, attribut, libelle, d, index, champ, mode, prof, vus):
        """``<Composant attribut={fn} />`` : le composant lit ``attribut`` dans
        ses props (1er paramètre destructuré) et l'appelle dans son corps."""
        res = Resultat()
        raison = f"{libelle} passée en prop « {attribut} » (paramètres invisibles)"
        balises = list(re.finditer(r"<([A-Z][\w$]*)\b", rmod.masked[max(0, b - 3000):b]))
        if not balises:
            return self._inconnu(rmod, d, raison, res, mode, rmod.declaration(d))
        nom_c = balises[-1].group(1)
        candidats = [(rmod, t) for t in rmod.tetes if t.nom == nom_c]
        if not candidats:
            for hmod in self.modules:
                if hmod.rel in rmod.imports:
                    candidats += [(hmod, t) for t in hmod.tetes if t.nom == nom_c]
        trouve = False
        for hmod, ht in candidats:
            for idx, pnom, pch in ht.params:
                if idx == 0 and pch == attribut:
                    trouve = True
                    res.fusion(self._corps(hmod, ht, pnom, index, champ, mode, prof, vus))
        if not trouve:
            return self._inconnu(rmod, d, raison + f" de « {nom_c} »", res, mode,
                                 rmod.declaration(d))
        return res

    def _enveloppe(self, rmod, pos_h, nom_h, index, champ, mode, prof, vus, d):
        """``const NOM = createAsyncThunk('x', (arg) => …)`` / ``useCallback`` :
        les appelants de NOM fournissent les arguments de la fonction."""
        res = Resultat()
        avant = rmod.masked[max(0, pos_h - 120):pos_h]
        nm = re.search(r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:await\s+)?$", avant)
        if not nm and re.search(r"\breturn\s*$", avant):
            # `return createAsyncThunk(…)` dans une fabrique de thunks
            # (createCancellableThunk) : on remonte au site d'appel de la
            # fabrique, connu par la liaison de ses paramètres.
            for t in rmod.tetes_contenant(pos_h):
                for _, pnom, _ in t.params:
                    lien = self.env.get((rmod.rel, t.debut, pnom))
                    if lien is None:
                        continue
                    bmod, a = lien[0], lien[1]
                    appel = bmod.enclos(a)
                    hm = re.search(r"([A-Za-z_$][\w$]*)\s*$", bmod.masked[max(0, appel - 80):appel])
                    if appel >= 0 and hm:
                        sauve, self.env = self.env, lien[3]
                        try:
                            return self._enveloppe(bmod, appel - len(hm.group(0)), hm.group(1), index,
                                                   champ, mode, prof + 1, vus, d)
                        finally:
                            self.env = sauve
                break
        if not nm:
            return self._inconnu(rmod, d, f"fonction passée à « {nom_h} » sans nom", res, mode,
                                 rmod.declaration(d))
        nom = nm.group(1)
        debut = pos_h - len(avant) + nm.start(1)
        faux = Tete(debut, nom, [], pos_h, pos_h)
        genre = "fonction" if rmod.enclos(debut) < 0 else "locale"
        appelants, references = self.sites(rmod, faux, genre)
        res.fusion(self._depuis_appelants(appelants, nom, index, champ, mode, prof, vus))
        for xmod, xpos in references:
            x = xpos
            while x > 0 and (xmod.masked[x - 1].isalnum() or xmod.masked[x - 1] in "_$.?"):
                x -= 1
            if not self._est_passage(xmod, x, xpos + len(nom)):
                continue
            res.fusion(self._passee(xmod, x, xpos + len(nom), f"« {nom} »", index, champ, mode,
                                    prof + 1, vus))
        return res

    # -- URL : littéral, constante, ternaire, locale, ou paramètre suivi -------
    def urls(self, mod, s, e, prof=0):
        """[(module, pos, brut, quote, env)] — toutes les URL possibles de
        l'expression [s, e). Une URL paramètre d'une fonction nommée est suivie
        jusqu'à CHAQUE appelant, avec l'environnement de liaison de ce site
        (ses ``params`` sont alors résolus pour CE site)."""
        s, e = _rogner(mod.code, s, e)
        texte = mod.code[s:e]
        if not texte or prof > PROFONDEUR_MAX:
            return []
        if s in mod.token_at and mod.token_at[s][0] >= e:
            _, quote, raw = mod.token_at[s]
            return [(mod, s, raw, quote, self.env)]
        if mod.masked[s] == "(" and _apparier(mod.masked, s) == e - 1:
            return self.urls(mod, s + 1, e - 1, prof)
        branches = self._ternaire(mod, s, e)
        if branches:
            return [u for a, b in branches for u in self.urls(mod, a, b, prof)]
        if not IDENT.match(texte):
            return []
        decl_pos = None
        for m in re.finditer(r"\b(?:const|let|var)\s+%s\s*=(?!=)" % re.escape(texte),
                             mod.masked[:s]):
            decl_pos = m
        tete, position = None, None
        for t in mod.tetes_contenant(s):
            p = t.position_de(texte)
            if p is not None:
                tete, position = t, p
                break
        if decl_pos is not None and (tete is None or decl_pos.start() > tete.debut):
            debut = decl_pos.end()
            return self.urls(mod, debut, _fin_expression(mod.masked, debut), prof)
        if tete is None:
            const = mod.consts.get(texte)
            return [(mod, s, const, "'", self.env)] if isinstance(const, str) else []
        cle = (mod.rel, tete.debut, texte)
        if cle in self.env:
            lien = self.env[cle]
            if lien is None or lien[4] is not None:
                return []
            bmod, a, b, benv, _ = lien
            sauve, self.env = self.env, benv
            try:
                return self.urls(bmod, a, b, prof + 1)
            finally:
                self.env = sauve
        if not tete.nom or position[1] is not None:
            return []
        sortie = []
        appelants, _ = self.sites(mod, tete)
        for cmod, ouvre in appelants:
            args = _decouper(cmod.masked, ouvre + 1, _apparier(cmod.masked, ouvre))
            if position[0] >= len(args):
                continue
            env = dict(self.env)
            for idx, pnom, pch in tete.params:
                env[(mod.rel, tete.debut, pnom)] = (
                    (cmod,) + args[idx] + (self.env, pch) if idx < len(args) else None)
            a, b = args[position[0]]
            for u in self.urls(cmod, a, b, prof + 1):
                sortie.append(u[:4] + (env,))
        return sortie

    def _champ(self, mod, s, e, champ, mode, prof, vus):
        """Valeur du champ ``champ`` de l'argument objet [s, e)."""
        res = Resultat()
        s, e = _rogner(mod.code, s, e)
        if mod.masked[s:s + 1] == "{" and _apparier(mod.masked, s) == e - 1:
            for a, b in _decouper(mod.masked, s + 1, e - 1):
                texte = mod.code[a:b]
                if texte.startswith("..."):
                    return self._inconnu(mod, a, f"étalement dans l'argument (champ {champ})",
                                         res, mode, mod.declaration(a))
                mm = re.match(r"([A-Za-z_$][\w$]*)\s*(:)?", texte)
                if mm and mm.group(1) == champ:
                    if mm.group(2):
                        return self.cles(mod, a + mm.end(), b, mode, prof, vus)
                    return self._identifiant(mod, champ, a, mode, prof, vus, mod.declaration(a))
            return res
        return self._inconnu(mod, s, f"argument non littéral (champ {champ})", res, mode,
                             mod.declaration(s))


def _court(texte: str, n: int = 60) -> str:
    texte = " ".join(texte.split())
    return texte if len(texte) <= n else texte[:n - 1] + "…"


def _noms_chaine_requete(raw: str, quote: str) -> list:
    """Noms d'une chaîne de requête littérale ``a=1&b=${x}`` (sans le ``?``)."""
    noms = []
    for part in re.split(r"[&]", raw.lstrip("?")):
        cle = part.split("=", 1)[0].strip()
        if cle and "${" not in cle and re.match(r"^[\w.\[\]-]+$", cle):
            noms.append(cle)
    return noms


# ===========================================================================
# 4. Appels HTTP et liens directs
# ===========================================================================

_TROU = re.compile(r"\$\{([^{}]*)\}")
_TERNAIRE = re.compile(r"^[^?]+\?\s*('[^']*'|\"[^\"]*\")\s*:\s*('[^']*'|\"[^\"]*\")$")


def _morceaux_gabarit(raw: str) -> list:
    """[("lit", texte) | ("trou", expression)] d'un gabarit ``${…}``."""
    morceaux, pos = [], 0
    for m in _TROU.finditer(raw):
        morceaux.append(("lit", raw[pos:m.start()]))
        morceaux.append(("trou", m.group(1).strip()))
        pos = m.end()
    morceaux.append(("lit", raw[pos:]))
    return morceaux


def _verser_litteral(chemin: str, dans_requete: bool, requete: str, texte: str) -> tuple:
    """Verse ``texte`` dans le chemin ou, une fois passé le ``?``, dans la requête."""
    if not dans_requete and "?" in texte:
        avant, _, apres = texte.partition("?")
        return chemin + avant, True, requete + apres
    if dans_requete:
        return chemin, dans_requete, requete + texte
    return chemin + texte, dans_requete, requete


def _noms_requete_reconstituee(requete: str, ori: str, res) -> None:
    """Verse dans ``res`` les noms de la requête reconstituée par ``decouper_url``."""
    for part in requete.split("&"):
        cle = part.split("=", 1)[0].strip()
        if not cle or cle == "\x01":
            continue
        if HOLE in cle or "\x01" in cle:
            res.inconnu(ori, "clé de requête calculée dans le gabarit")
            continue
        if re.match(r"^[\w.\[\]-]+$", cle):
            res.nom(cle, ori)


def decouper_url(analyse, mod, debut_jeton, raw, quote):
    """(chemin avec trous, Resultat des noms de la chaîne de requête, non_résolu?)"""
    res = Resultat()
    ori = analyse.ori(mod, debut_jeton)
    if quote != "`":
        chemin, _, requete = raw.partition("?")
        for nom in _noms_chaine_requete(requete, quote):
            res.nom(nom, ori)
        return chemin, res
    # Gabarit : remplacer les trous, en notant ceux de la requête.
    chemin, dans_requete, requete = "", False, ""
    for genre, valeur in _morceaux_gabarit(raw):
        if genre == "lit":
            chemin, dans_requete, requete = _verser_litteral(chemin, dans_requete, requete, valeur)
            continue
        const = mod.consts.get(valeur)
        fm = re.fullmatch(r"([A-Za-z_$][\w$]*)\s*\(.*\)", valeur, re.S)
        if const is None and fm:
            # `${pivot(id)}` : fonction du frontend qui rend un gabarit
            const = analyse.gabarit_fonction(mod, fm.group(1))
        ternaire = _TERNAIRE.match(valeur)
        if isinstance(const, str):
            chemin, dans_requete, requete = _verser_litteral(chemin, dans_requete, requete, const)
            continue
        if ternaire:
            branches = [ternaire.group(1)[1:-1], ternaire.group(2)[1:-1]]
            if all(b == "" or b.startswith("?") or b.startswith("&") for b in branches):
                for b in branches:
                    for nom in _noms_chaine_requete(b, "'"):
                        res.nom(nom, ori)
                continue
        if dans_requete:
            fin_req = requete.rstrip()
            if fin_req == "" or fin_req.endswith("&"):
                # ?${qs} / &${qs} : une chaîne de requête entière
                res.fusion(_cles_texte(analyse, mod, debut_jeton, valeur))
                requete += "\x01"
            else:
                requete += HOLE  # valeur d'un paramètre
            continue
        chemin += HOLE
    _noms_requete_reconstituee(requete, ori, res)
    chemin = resolve_template(chemin, "'", mod.consts) or chemin
    return chemin, res


def _cles_texte(analyse, mod, pos, expression):
    """Trou ``${expr}`` en position de chaîne de requête entière."""
    expr = expression.strip()
    if expr.endswith(".toString()"):
        expr = expr[:-len(".toString()")].strip()
    if IDENT.match(expr):
        return analyse._identifiant(mod, expr, pos, "params", 0, frozenset(),
                                    mod.declaration(pos))
    res = Resultat()
    decl = mod.declaration(pos)
    return analyse._inconnu(mod, pos, f"chaîne de requête calculée « {_court(expr)} »",
                            res, "params", decl)


class Envoi:
    """Un envoi : site d'appel, méthode, segments, noms + non résolus."""

    __slots__ = ("ori", "methode", "segments", "chemin", "res")

    def __init__(self, ori, methode, segments, chemin, res):
        self.ori, self.methode, self.segments = ori, methode, segments
        self.chemin, self.res = chemin, res


def _http(analyse, mod, envois, stats):
    sites_url = set()
    motif = re.compile(r"([A-Za-z_$][\w$.]*)\.(get|post|put|patch|delete|head|options)\s*\(")
    for m in motif.finditer(mod.masked):
        client, methode = m.group(1), m.group(2)
        if not CLIENT_HINT.search(client.split(".")[-1]) and client not in ("axios",):
            continue
        ouvre = m.end() - 1
        args = _decouper(mod.masked, ouvre + 1, _apparier(mod.masked, ouvre))
        if not args:
            continue
        if any(t.nom in MODELISEES for t in mod.tetes_contenant(m.start())):
            continue  # fabrique modélisée à part (voir _fabriques)
        stats["appels"] += 1
        ua, ub = args[0]
        sites_url.add(ua)
        idx = HTTP_URL_CONFIG[methode]
        site = analyse.ori(mod, m.start())
        urls = analyse.urls(mod, ua, ub)
        chemins_declares = mod.chemins_declares(ua)
        if not urls and chemins_declares:
            # URL servie par le serveur (jamais construite ici) : la
            # déclaration `chemins-requete:` posée à côté nomme les gabarits
            # possibles ; les paramètres sont vérifiés contre CHACUN.
            for gabarit in chemins_declares:
                chemin = re.sub(r"\{[^}/]*\}", HOLE, gabarit)
                res = Resultat()
                if idx < len(args):
                    res.fusion(analyse.cles(mod, args[idx][0], args[idx][1], "config", 0))
                envois.append(Envoi(site, methode, normalise_call(chemin, MOUNT), chemin, res))
            continue
        if not urls:
            res = Resultat()
            if idx < len(args):
                res.fusion(analyse.cles(mod, args[idx][0], args[idx][1], "config", 0))
            if res.noms or res.non_resolus or "?" in mod.code[ua:ub]:
                stats["url_dynamique"] += 1
                res.inconnu(analyse.ori(mod, ua),
                            f"URL dynamique « {_court(mod.code[ua:ub])} » avec paramètres")
                envois.append(Envoi(site, methode, None, None, res))
            continue
        for umod, upos, raw, quote, env in urls:
            sauve, analyse.env = analyse.env, env
            try:
                chemin, res = decouper_url(analyse, umod, upos, raw, quote)
                if idx < len(args):
                    res.fusion(analyse.cles(mod, args[idx][0], args[idx][1], "config", 0))
            finally:
                analyse.env = sauve
            envois.append(Envoi(site, methode, normalise_call(chemin, MOUNT), chemin, res))
    # liens directs /api/django/…?x=
    for debut, fin, quote, raw in mod.tokens:
        if debut in sites_url or not raw.startswith(f"/{MOUNT}/") or "?" not in raw:
            continue
        stats["liens"] += 1
        chemin, r = decouper_url(analyse, mod, debut, raw, quote)
        envois.append(Envoi(analyse.ori(mod, debut), "get",
                            normalise_call(chemin, MOUNT), chemin, r))


def _fabriques(analyse, mod, envois, stats):
    """Fabrique CRUD partagée (``api/resource.js``) : ``const crud =
    makeResourceFactory(api, '/tiers')`` puis ``tiers: crud('tiers')`` (ou
    ``campaigns: { ...resource('campaigns') }``) — son ``list(params)`` fait
    ``GET <base>/<slug>/`` avec ``params``. Modélisé ici : chaque
    ``<clé>.list(…)`` des modules clients devient un envoi vers ce chemin."""
    m = mod.masked
    for fm in re.finditer(r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*makeResourceFactory\s*\(",
                          m):
        ouvre = fm.end() - 1
        args = _decouper(m, ouvre + 1, _apparier(m, ouvre))
        if len(args) < 2:
            continue
        a, b = args[1]
        base = mod.token_at[a][2] if a in mod.token_at else mod.consts.get(mod.code[a:b].strip())
        if not isinstance(base, str):
            continue
        base = base.rstrip("/") + "/"
        for appel in re.finditer(r"(?<![\w$.])%s\s*\(" % re.escape(fm.group(1)), m):
            debut = appel.end()
            fin = _apparier(m, appel.end() - 1)
            jeton = _rogner(mod.code, debut, fin)[0]
            if jeton not in mod.token_at:
                continue
            slug = mod.token_at[jeton][2]
            # clé qui porte l'objet : `const k = crud(…)`, `k: crud(…)`, ou la
            # clé de l'objet englobant (`k: { ...crud(…) }`).
            avant = m[max(0, appel.start() - 80):appel.start()]
            km = re.search(r"(?:(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=|([A-Za-z_$][\w$]*)\s*:)\s*$",
                           avant)
            cle = (km.group(1) or km.group(2)) if km else None
            pos = appel.start()
            while cle is None:
                b = mod.enclos(pos)
                if b < 0:
                    break
                km = re.search(r"([A-Za-z_$][\w$]*)\s*:\s*$", m[max(0, b - 80):b])
                if m[b] == "{" and km:
                    cle = km.group(1)
                pos = b
            if cle is None:
                res = Resultat()
                res.inconnu(analyse.ori(mod, appel.start()), "objet de fabrique CRUD sans clé lisible")
                envois.append(Envoi(analyse.ori(mod, appel.start()), "get", None, None, res))
                continue
            chemin = f"{base}{slug}/"
            clients = analyse._modules_clients(mod)
            ids = {id(x) for x in clients}
            for cmod, occ in analyse.pointes.get("list", ()):
                if id(cmod) not in ids or occ.group(1) != cle:
                    continue
                suite = cmod.masked[occ.end(2):occ.end(2) + 20]
                ap = re.match(r"\s*(?:\?\.)?\s*\(", suite)
                if not ap:
                    continue
                o2 = occ.end(2) + ap.end() - 1
                args2 = _decouper(cmod.masked, o2 + 1, _apparier(cmod.masked, o2))
                res = Resultat()
                if args2:
                    res.fusion(analyse.cles(cmod, args2[0][0], args2[0][1], "params", 0))
                stats["appels"] += 1
                envois.append(Envoi(analyse.ori(cmod, o2), "get",
                                    normalise_call(chemin, MOUNT), chemin, res))


def endpoints_entite(texte: str) -> list:
    """Regex de ENDPOINTS_ENTITE relues dans axios.js (modèle de l'intercepteur)."""
    m = re.search(r"ENDPOINTS_ENTITE\s*=\s*\[(.*?)\]\s*\n", texte, re.S)
    if not m:
        return []
    motifs = []
    for lit in re.findall(r"/((?:\\/|[^/\n])+)/[gimsuy]*\s*,?", m.group(1)):
        motifs.append(re.compile(lit.replace("\\/", "/")))
    return motifs


# ===========================================================================
# 5. Verdict
# ===========================================================================

def analyser(fichiers=None, contrat_texte=None, axios_texte=None):
    fichiers = frontend_files() if fichiers is None else fichiers
    if contrat_texte is None:
        contrat_texte = SNAPSHOT_PATH.read_text(encoding="utf-8")
    if axios_texte is None:
        axios_texte = AXIOS_PATH.read_text(encoding="utf-8") if AXIOS_PATH.is_file() else ""
    contrat = Contrat(charger_contrat(contrat_texte))
    modules = []
    for path in fichiers:
        try:
            src = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        modules.append(Module(path, src))
    analyse = Analyse(modules, endpoints_entite(axios_texte))
    envois = []
    stats = {"fichiers": len(modules), "appels": 0, "liens": 0, "url_dynamique": 0,
             "envois_avec_parametres": 0, "parametres_verifies": 0, "hors_schema": 0}
    for mod in modules:
        _http(analyse, mod, envois, stats)
        _fabriques(analyse, mod, envois, stats)

    constats, non_resolus = set(), set()
    for envoi in envois:
        res = envoi.res
        if envoi.methode == "get" and envoi.chemin is not None:
            plein = envoi.chemin if envoi.chemin.startswith("/api/") else f"/{MOUNT}{envoi.chemin}"
            plein = plein.replace(HOLE, "x")
            if any(r.search(plein) for r in analyse.entite):
                res.nom("entite", "frontend/src/api/axios.js (intercepteur ENDPOINTS_ENTITE)")
        for ori, raison in res.non_resolus:
            non_resolus.add((ori, raison, envoi.ori))
        if not res.noms:
            continue
        stats["envois_avec_parametres"] += 1
        if envoi.segments is None:
            if envoi.chemin is not None and not res.non_resolus:
                non_resolus.add((envoi.ori, f"chemin non rattachable au schéma « "
                                 f"{_court(envoi.chemin.replace(HOLE, '${…}'))} »", envoi.ori))
            continue
        autorises = contrat.autorises(envoi.methode, envoi.segments)
        if autorises is None:
            stats["hors_schema"] += 1
            stats.setdefault("hors_schema_detail", []).append(
                f"{envoi.ori} {envoi.methode.upper()} {envoi.chemin.replace(HOLE, '{…}')}")
            continue
        operation = "/" + "/".join("{…}" if s == ANY else s for s in envoi.segments) + "/"
        for nom, origines in res.noms.items():
            stats["parametres_verifies"] += 1
            if nom in autorises or nom in PARAMETRES_PLATEFORME:
                continue
            constats.add((envoi.ori, envoi.methode.upper(), operation, nom,
                          ", ".join(sorted(origines))))
    stats["passe_plats"] = len(analyse.passe_plats)
    return sorted(constats), sorted(non_resolus), stats


def cle_constat(c) -> str:
    return f"ECHEC|{c[0].split(':')[0]}|{c[1]}|{c[2]}|{c[3]}"


def cle_non_resolu(n) -> str:
    return f"NON-RESOLU|{n[0].split(':')[0]}|{n[1]}"


def charger_exceptions(path: Path = ALLOW_PATH) -> dict:
    """{clé: raison}. Format : ``clé  # raison`` — une raison est obligatoire."""
    entrees = {}
    if not path.is_file():
        return entrees
    for ligne in path.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#"):
            continue
        cle, _, raison = ligne.partition("  # ")
        entrees[cle.strip()] = raison.strip()
    return entrees


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--stats", action="store_true", help="inventaire chiffré")
    args = parser.parse_args(argv)

    constats, non_resolus, stats = analyser()
    exceptions = charger_exceptions()
    utilisees = set()
    echecs = 0

    rouges = []
    for c in constats:
        cle = cle_constat(c)
        if cle in exceptions:
            utilisees.add(cle)
            continue
        rouges.append(c)
    flous = []
    for n in non_resolus:
        cle = cle_non_resolu(n)
        if cle in exceptions:
            utilisees.add(cle)
            continue
        flous.append(n)

    for ori, methode, operation, nom, origines in rouges:
        print(f"ECHEC : {ori} — {methode} {operation} envoie « ?{nom}= », "
              f"non déclaré par l'opération (nom écrit en {origines})")
        echecs += 1
    for ori, raison, site in flous:
        print(f"ECHEC : NON RÉSOLU {ori} — {raison} (appel HTTP {site})")
        echecs += 1
    sans_raison = [c for c, r in exceptions.items() if not r]
    for cle in sans_raison:
        print(f"ECHEC : exception sans raison dans {ALLOW_PATH.name} : {cle}")
        echecs += 1
    for cle in sorted(set(exceptions) - utilisees):
        print(f"ECHEC : exception devenue inutile (à retirer de {ALLOW_PATH.name}) : {cle}")
        echecs += 1

    if args.stats or echecs:
        print(f"\nInventaire : {stats['fichiers']} fichiers, {stats['appels']} appels HTTP, "
              f"{stats['liens']} liens directs, {stats['envois_avec_parametres']} envois "
              f"avec paramètres, {stats['parametres_verifies']} paramètres vérifiés, "
              f"{stats['passe_plats']} passe-plats remontés, {stats['hors_schema']} envoi(s) "
              f"hors schéma (domaine de check_api_contract.py), {len(exceptions)} exception(s).")
        for ligne in stats.get("hors_schema_detail", []):
            print(f"  hors schéma : {ligne}")
    if echecs:
        print(f"\n{len(rouges)} paramètre(s) non déclaré(s), {len(flous)} expression(s) non "
              f"résolue(s).\nREMÈDE : déclarer le paramètre sur la vue "
              f"(@extend_schema(parameters=[OpenApiParameter(...)]) — la vue doit le LIRE), "
              f"ou le retirer de l'appel frontend s'il est ignoré ; pour une expression "
              f"dynamique, la rendre lisible ou poser « // parametres-requete: a, b » à côté.\n"
              f"Puis régénérer l'instantané : python scripts/check_openapi_schema.py --write")
        return 1
    print(f"OK : aucun paramètre de requête frontend hors contrat "
          f"({stats['parametres_verifies']} vérifiés).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
