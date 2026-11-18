"""Tests ADEP5 — `Cache-Control: no-store` sur l'API seulement (backend/nginx/nginx.conf).

Stdlib pure (unittest), aucune image nginx. Run :
    python -m unittest scripts.tests.test_nginx_cache_control -v

Le test lit la configuration réelle et résout les `add_header` EFFECTIFS par
location selon la règle d'héritage nginx : une location qui déclare au moins un
`add_header` n'hérite PLUS d'aucun `add_header` du niveau server. Les `include`
du fragment d'en-têtes de sécurité (généré au démarrage depuis
`security-headers.conf.template`) sont résolus vers le gabarit. Une valeur
d'en-tête qui est une variable (`$cache_ctl`) est évaluée via le bloc `map`
correspondant : une valeur vide ⇒ nginx n'émet pas l'en-tête.

Le mini-analyseur (`analyser`, `server_principal`, `location_pour`,
`entetes_effectifs`) est réutilisé par les tests nginx ASEC47 / ASEC52.

ADEP106 (`JournalJetonMasqueTests`) : le jeton du calendrier abonné de Tâches ne
sort en clair d'aucun journal de nginx ; `motifs_django` / `masque_django` sont
réutilisés par le jumeau Caddy (test_caddyfile_adep103_relais.py).
"""
import ast
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.tests import test_auto_deploy as deploy  # banc bash partagé (_bash, _px)

ROOT = Path(__file__).resolve().parent.parent.parent
NGINX_DIR = ROOT / "backend" / "nginx"
NGINX_CONF = NGINX_DIR / "nginx.conf"

# include généré au démarrage → gabarit versionné
INCLUDES = {
    "/etc/nginx/generated/security-headers.conf":
        NGINX_DIR / "security-headers.conf.template",
}

ENTETES_SECURITE = (
    "X-Frame-Options",
    "X-Content-Type-Options",
    "Content-Security-Policy",
    "Strict-Transport-Security",
    "Referrer-Policy",
)


# ── mini-analyseur nginx ─────────────────────────────────────────────────────
def _jetons(texte):
    """Découpe en jetons : mots, chaînes entre guillemets, `{`, `}`, `;`."""
    jetons = []
    i, n = 0, len(texte)
    while i < n:
        c = texte[i]
        if c.isspace():
            i += 1
        elif c == "#":
            while i < n and texte[i] != "\n":
                i += 1
        elif c in "{};":
            jetons.append(c)
            i += 1
        elif c in "\"'":
            j = i + 1
            while j < n and texte[j] != c:
                if texte[j] == "\\":
                    j += 1
                j += 1
            jetons.append(("Q", texte[i + 1:j]))
            i = j + 1
        else:
            j = i
            while j < n and not texte[j].isspace() and texte[j] not in "{};":
                j += 1
            jetons.append(texte[i:j])
            i = j
    return jetons


def _valeur(jeton):
    return jeton[1] if isinstance(jeton, tuple) else jeton


def _blocs(jetons, pos=0):
    """Renvoie (liste de directives, position). Directive = (nom, args, enfants|None)."""
    directives = []
    courant = []
    while pos < len(jetons):
        j = jetons[pos]
        if j == ";":
            if courant:
                directives.append((_valeur(courant[0]), [_valeur(x) for x in courant[1:]], None))
            courant = []
            pos += 1
        elif j == "{":
            enfants, pos = _blocs(jetons, pos + 1)
            directives.append((_valeur(courant[0]), [_valeur(x) for x in courant[1:]], enfants))
            courant = []
        elif j == "}":
            return directives, pos + 1
        else:
            courant.append(j)
            pos += 1
    return directives, pos


def _developper_includes(directives):
    sortie = []
    for nom, args, enfants in directives:
        if nom == "include" and args and args[0] in INCLUDES:
            inclus, _ = _blocs(_jetons(INCLUDES[args[0]].read_text(encoding="utf-8")))
            sortie.extend(_developper_includes(inclus))
        elif enfants is not None:
            sortie.append((nom, args, _developper_includes(enfants)))
        else:
            sortie.append((nom, args, None))
    return sortie


def analyser(chemin=NGINX_CONF):
    texte = Path(chemin).read_text(encoding="utf-8")
    directives, _ = _blocs(_jetons(texte))
    return _developper_includes(directives)


def bloc_http(arbre):
    return next(e for n, _, e in arbre if n == "http")


def server_principal(arbre):
    """Le server qui écoute sur 80 (pas l'écouteur public 8090 du tunnel)."""
    for nom, _, enfants in bloc_http(arbre):
        if nom == "server" and any(n == "listen" and a and a[0] == "80"
                                   for n, a, _ in enfants):
            return enfants
    raise AssertionError("server listen 80 introuvable dans nginx.conf")


def locations(server):
    """[(modificateur, motif, enfants)] dans l'ordre du fichier."""
    sortie = []
    for nom, args, enfants in server:
        if nom == "location":
            if len(args) == 2:
                sortie.append((args[0], args[1], enfants))
            else:
                sortie.append(("", args[0], enfants))
    return sortie


def location_pour(server, uri):
    """Sélection nginx (simplifiée) : `=` exact, puis plus long préfixe, puis regex."""
    locs = locations(server)
    for mod, motif, enfants in locs:
        if mod == "=" and motif == uri:
            return motif, enfants
    meilleur = None
    for mod, motif, enfants in locs:
        if mod in ("", "^~") and uri.startswith(motif):
            if meilleur is None or len(motif) > len(meilleur[0]):
                meilleur = (motif, enfants, mod)
    if meilleur and meilleur[2] == "^~":
        return meilleur[0], meilleur[1]
    for mod, motif, enfants in locs:
        if mod in ("~", "~*"):
            drapeaux = re.IGNORECASE if mod == "~*" else 0
            if re.search(motif, uri, drapeaux):
                return motif, enfants
    if meilleur:
        return meilleur[0], meilleur[1]
    raise AssertionError(f"aucune location pour {uri}")


def _map_valeur(arbre, variable, entree):
    """Évalue `map <source> $variable { ... }` pour la valeur source `entree`."""
    for nom, args, enfants in bloc_http(arbre):
        if nom == "map" and len(args) == 2 and args[1] == variable:
            defaut = ""
            for cle, vals, _ in enfants:
                val = vals[0] if vals else ""
                if cle == "default":
                    defaut = val
                elif cle.startswith("~*"):
                    if re.search(cle[2:], entree, re.IGNORECASE):
                        return val
                elif cle.startswith("~"):
                    if re.search(cle[1:], entree):
                        return val
                elif cle == entree:
                    return val
            return defaut
    raise AssertionError(f"map {variable} introuvable")


def entetes_effectifs(arbre, uri):
    """{nom d'en-tête: valeur} réellement émis pour `uri` (règle d'héritage nginx)."""
    server = server_principal(arbre)
    _, loc = location_pour(server, uri)
    propres = [a for n, a, _ in loc if n == "add_header"]
    source = propres if propres else [a for n, a, _ in server if n == "add_header"]
    sortie = {}
    for args in source:
        nom, valeur = args[0], args[1] if len(args) > 1 else ""
        if valeur.startswith("$"):
            valeur = _map_valeur(arbre, valeur, uri)
        if valeur == "":
            continue  # nginx n'émet pas un en-tête de valeur vide
        sortie[nom] = valeur
    return sortie


FOND_CARTE = ROOT / "frontend" / "src" / "lib" / "calage" / "fondCarte.js"
ENTRYPOINT = NGINX_DIR / "docker-entrypoint.sh"
# envsubst minimal (seules les variables listées en argument), comme gettext.
_ENVSUBST = r'''import os, re, sys
noms = re.findall(r"\$\{(\w+)\}", " ".join(sys.argv[1:]))
texte = sys.stdin.read()
for nom in noms:
    texte = texte.replace("${" + nom + "}", os.environ.get(nom, ""))
sys.stdout.write(texte)
'''


def _csp_rendue(dsn):
    """ADCG53 — rend le gabarit par le VRAI docker-entrypoint.sh (chemins
    /etc/nginx déplacés dans un dossier temporaire) ; {directive: [jetons]}."""
    with tempfile.TemporaryDirectory() as d:
        racine = Path(d)
        (racine / "templates").mkdir()
        shutil.copy(NGINX_DIR / "security-headers.conf.template", racine / "templates")
        (racine / "envsubst.py").write_text(_ENVSUBST, encoding="utf-8")
        shim = racine / "bin" / "envsubst"
        shim.parent.mkdir()
        shim.write_text(f'#!/usr/bin/env bash\nexec "{deploy._px(sys.executable)}" '
                        f'"{deploy._px(racine / "envsubst.py")}" "$@"\n', encoding="utf-8")
        shim.chmod(0o755)
        script = racine / "entrypoint.sh"
        script.write_bytes(ENTRYPOINT.read_text(encoding="utf-8")
                           .replace("/etc/nginx", deploy._px(racine))
                           .replace("\r\n", "\n").encode())
        subprocess.run([deploy._bash(), "-c", 'export PATH="$1:$PATH"; sh "$2" true', "_",
                        deploy._px(shim.parent), deploy._px(script)],
                       env={**os.environ, "VITE_SENTRY_DSN": dsn}, check=True,
                       capture_output=True, timeout=60)
        texte = (racine / "generated" / "security-headers.conf").read_text(encoding="utf-8")
    valeur = re.search(r'Content-Security-Policy "([^"]+)"', texte).group(1)
    return {d.split()[0]: d.split()[1:] for d in valeur.split(";") if d.strip()}


# ── tests ADEP5 ──────────────────────────────────────────────────────────────
class CacheControlTests(unittest.TestCase):
    def setUp(self):
        self.arbre = analyser()

    def test_assets_sans_no_store(self):
        for uri in ("/", "/assets/index-CJBAo8Lb.js", "/ventes/devis"):
            cc = entetes_effectifs(self.arbre, uri).get("Cache-Control", "")
            self.assertNotIn("no-store", cc, f"{uri} porte encore no-store")

    def test_api_garde_no_store(self):
        for uri in ("/api/django/auth/me/", "/api/django/token/", "/api/fastapi/ocr/"):
            cc = entetes_effectifs(self.arbre, uri).get("Cache-Control", "")
            self.assertIn("no-store", cc, f"{uri} a perdu no-store")

    def test_entetes_securite_presents(self):
        for uri in ("/", "/assets/index-CJBAo8Lb.js", "/api/django/auth/me/"):
            entetes = entetes_effectifs(self.arbre, uri)
            for nom in ENTETES_SECURITE:
                self.assertIn(nom, entetes, f"{nom} absent sur {uri}")

    def test_csp_couvre_les_origines_externes_du_front(self):
        """ADCG53 — chaque origine https:// de fondCarte.js est en img-src ; le DSN
        Sentry armé met son hôte en connect-src (rendu réel par l'entrypoint)."""
        csp = _csp_rendue("https://k@o1.ingest.de.sentry.io/2")
        for url in re.findall(r"https://[^'\"`\s]+", FOND_CARTE.read_text(encoding="utf-8")):
            origine = re.match(r"https://[^/?]+", url).group(0).replace("{s}", "*")
            self.assertIn(origine, csp["img-src"], f"{url} : origine absente de img-src")
        self.assertIn("https://o1.ingest.de.sentry.io", csp["connect-src"])
        sans_dsn = _csp_rendue("")
        self.assertEqual(
            sans_dsn["connect-src"],
            [t for t in csp["connect-src"] if t != "https://o1.ingest.de.sentry.io"])

    def test_aucun_no_store_litteral_au_niveau_server(self):
        server = server_principal(self.arbre)
        for nom, args, _ in server:
            if nom == "add_header" and args[0].lower() == "cache-control":
                self.assertTrue(args[1].startswith("$"),
                                "Cache-Control littéral au niveau server : hérité par /")


class ApiPubliqueServieTests(unittest.TestCase):
    """APUB15 (D-APUB-3) — l'API publique par clé est routée vers Django."""

    def test_api_publique_routee_vers_django(self):
        arbre = analyser()
        server = server_principal(arbre)
        attendus = {"Host", "X-Real-IP", "X-Forwarded-For"}
        for uri in ("/api/public/v1/leads/", "/api/public/v1/openapi.json",
                    "/api/public/v1/oauth/token/"):
            motif, loc = location_pour(server, uri)
            self.assertEqual(motif, "/api/public/", uri)
            directives = {n: a for n, a, _ in loc}
            self.assertEqual(directives.get("proxy_pass"), ["http://django_backend"], uri)
            self.assertIn("limit_req", directives, uri)
            entetes = {a[0]: a[1] for n, a, _ in loc if n == "proxy_set_header"}
            self.assertTrue(attendus <= set(entetes), uri)
            self.assertEqual(entetes.get("X-Forwarded-Proto"), "$proto_transmis", uri)
            self.assertIn("no-store", entetes_effectifs(arbre, uri).get("Cache-Control", ""), uri)
        self.assertEqual(location_pour(server, "/")[0], "/")


FRONT_NGINX = ROOT / "frontend" / "nginx.conf"


def _locations_front():
    """[(motif, enfants)] des locations du server de frontend/nginx.conf."""
    arbre, _ = _blocs(_jetons(FRONT_NGINX.read_text(encoding="utf-8")))
    server = next(e for n, _, e in arbre if n == "server")
    return [(a[-1] if a else "", e) for n, a, e in server if n == "location"]


class FrontNginxUnePolitiqueTests(unittest.TestCase):
    """ADEP5 (acceptation ADEP99 P2.4, 10/10/2026) : un asset hashé porte UNE ligne
    Cache-Control. `expires` + `add_header Cache-Control` dans la même location en émet
    DEUX (max-age=… puis public, immutable) — mesuré par curl sur la pile locale."""

    def test_aucune_location_ne_cumule_expires_et_cache_control(self):
        for motif, enfants in _locations_front():
            noms = [n for n, _, _ in enfants]
            cc = [a for n, a, _ in enfants if n == "add_header" and a and a[0].lower() == "cache-control"]
            self.assertFalse("expires" in noms and cc,
                             f"location {motif} : expires + add_header Cache-Control = deux en-têtes")

    def test_assets_hashes_une_politique_immutable_d_un_an(self):
        motif, enfants = next((m, e) for m, e in _locations_front() if "js|css" in m)
        cc = [a[1] for n, a, _ in enfants if n == "add_header" and a and a[0].lower() == "cache-control"]
        self.assertEqual(len(cc), 1, motif)
        for jeton in ("public", "max-age=31536000", "immutable"):
            self.assertIn(jeton, cc[0])


# ── ADEP106 — jeton du calendrier abonné de Tâches hors des journaux ─────────
AUTH_JETON = ROOT / "backend" / "django_core" / "apps" / "taches" / "auth_jeton.py"
# Valeurs d'EXEMPLE à la forme d'un clair émis (préfixe d'usage + caractères
# url-safe) — jamais un vrai jeton.
JETON_FLUX = "tqf_EXEMPLEjetonFACTICE0123456789abcdefghijklm"
JETON_CAPTURE = "tqc_EXEMPLEcaptureFACTICE0123456789abcdefghijk"
FLUX = "/api/django/taches/flux/"
# Variables nginx qui portent l'adresse (ou un morceau) telle que le client l'a envoyée.
ADRESSES_BRUTES = {
    "request", "request_uri", "uri", "document_uri", "args", "query_string",
    "http_referer", "request_filename", "request_body", "sent_http_location",
    "upstream_http_location",
}
# (ligne reçue, ligne écrite) — au plus UNE occurrence par motif (limite d'une `map`).
LIGNES_A_SECRET = (
    (f"GET {FLUX}abc123.ics HTTP/1.1", f"GET {FLUX}<jeton>.ics HTTP/1.1"),
    (f"GET {FLUX}{JETON_FLUX}.ics HTTP/1.1", f"GET {FLUX}<jeton>.ics HTTP/1.1"),
    (f"HEAD {FLUX}{JETON_FLUX}.ics?plage=30 HTTP/1.0",
     f"HEAD {FLUX}<jeton>.ics?plage=30 HTTP/1.0"),
    # `.ics` oublié, `/` encodés (Django route quand même), adresse collée dans une recherche
    (f"GET {FLUX}{JETON_FLUX} HTTP/1.1", f"GET {FLUX}<jeton> HTTP/1.1"),
    (f"GET /api/django/taches%2Fflux%2F{JETON_FLUX}.ics HTTP/1.1",
     "GET /api/django/taches%2Fflux%2F<jeton>.ics HTTP/1.1"),
    (f"GET /api/django/recherche/?q=https%3A%2F%2Fapi.taqinor.ma%2Fapi%2Fdjango%2Ftaches%2Fflux%2F{JETON_FLUX}.ics"
     " HTTP/1.1",
     "GET /api/django/recherche/?q=https%3A%2F%2Fapi.taqinor.ma%2Fapi%2Fdjango%2Ftaches%2Fflux%2F<jeton>.ics"
     " HTTP/1.1"),
    # clair de jeton isolé : préfixe d'usage gardé
    (f"GET /api/django/recherche/?q={JETON_FLUX} HTTP/1.1",
     "GET /api/django/recherche/?q=tqf_<jeton> HTTP/1.1"),
    (f"GET /api/django/taches/flu/{JETON_FLUX}.ics HTTP/1.1",
     "GET /api/django/taches/flu/tqf_<jeton>.ics HTTP/1.1"),
    # les deux motifs sur la même ligne
    (f"GET {FLUX}{JETON_FLUX}.ics?q={JETON_CAPTURE} HTTP/1.1",
     f"GET {FLUX}<jeton>.ics?q=tqc_<jeton> HTTP/1.1"),
    # la forme d'un Referer
    (f"https://api.taqinor.ma{FLUX}{JETON_FLUX}.ics", f"https://api.taqinor.ma{FLUX}<jeton>.ics"),
)
AUTRES_LIGNES = (
    "GET / HTTP/1.1",
    "GET /api/django/crm/leads/?page=2&search=el%20amrani HTTP/1.1",
    "POST /api/django/token/ HTTP/1.1",
    "GET /api/django/taches/taches/?vue=aujourdhui HTTP/1.1",
    "GET /api/django/taches/flux/ HTTP/1.1",
    "GET /api/django/taches/fluxion/abc.ics HTTP/1.1",
    "GET /api/django/crm/leads/?q=tqf_trop_court HTTP/1.1",
    'GET /api/django/x/"guillemets"\\barre HTTP/1.1',
    "https://api.taqinor.ma/ventes/devis?x=1",
    "GARBAGE",
    "-",
)


def motifs_django():
    """([(nom, motif, remplacement)], masque) de `CHEMINS_SENSIBLES` — lus dans la
    source d'apps/taches/auth_jeton.py sans importer Django (constantes simples du
    module et leurs concaténations)."""
    constantes = {}

    def valeur(noeud):
        if isinstance(noeud, ast.Constant):
            return noeud.value
        if isinstance(noeud, ast.Name):
            return constantes[noeud.id]
        if isinstance(noeud, ast.BinOp) and isinstance(noeud.op, ast.Add):
            return valeur(noeud.left) + valeur(noeud.right)
        raise ValueError(ast.dump(noeud))

    for noeud in ast.parse(AUTH_JETON.read_text(encoding="utf-8")).body:
        if isinstance(noeud, ast.Assign) and len(noeud.targets) == 1 \
                and isinstance(noeud.targets[0], ast.Name):
            nom = noeud.targets[0].id
            if nom == "CHEMINS_SENSIBLES":
                motifs = [tuple(valeur(e) for e in entree.elts) for entree in noeud.value.elts]
                return motifs, constantes["MASQUE"]
            try:
                constantes[nom] = valeur(noeud.value)
            except (ValueError, KeyError):
                pass
    raise AssertionError("CHEMINS_SENSIBLES introuvable dans apps/taches/auth_jeton.py")


def masque_django(texte, occurrences=0):
    """`texte` tel que la brique Django le masque (`core.chemins_sensibles.masquer` :
    chaque motif, dans l'ordre), écrit avec `<jeton>`. `occurrences=1` : la première
    seulement de chaque motif — ce que sait faire une `map` nginx."""
    motifs, masque = motifs_django()
    for _, motif, remplacement in motifs:
        texte = re.sub(motif, remplacement, texte, count=occurrences)
    return texte.replace(masque, "<jeton>")


def _toutes_les_directives(directives):
    """Chaque (nom, args, enfants) de l'arbre, à toute profondeur."""
    for nom, args, enfants in directives:
        yield nom, args, enfants
        if enfants is not None:
            yield from _toutes_les_directives(enfants)


def _mot_nginx(mot):
    """Un mot de nginx.conf tel que nginx le lit : `\\"`, `\\'`, `\\\\` perdent leur
    barre, `\\t` `\\r` `\\n` deviennent le caractère ; toute autre barre est gardée
    (le `\\s` d'une expression régulière)."""
    def remplacer(m):
        c = m.group(1)
        if c in "\"'\\":
            return c
        return {"t": "\t", "r": "\r", "n": "\n"}.get(c, m.group(0))
    return re.sub(r"\\(.)", remplacer, mot)


def variable_journal(arbre, variable, contexte):
    """Valeur de `variable` pour un `contexte` {variable: valeur} : rejoue la `map`
    qui la définit comme nginx — clé exacte, puis expressions régulières dans l'ordre
    du fichier (jamais sur une valeur vide), puis `default` ; les captures nommées et
    les variables de la valeur sont recollées."""
    if variable in contexte:
        return contexte[variable]
    for nom, args, enfants in bloc_http(arbre):
        if nom == "map" and len(args) == 2 and args[1] == variable:
            source = variable_journal(arbre, args[0], contexte)
            entrees = [(_mot_nginx(cle), _mot_nginx(vals[0]) if vals else "")
                       for cle, vals, _ in enfants]
            gabarit, captures = dict(entrees).get("default", ""), {}
            exactes = {c: v for c, v in entrees if c != "default" and not c.startswith("~")}
            if source in exactes:
                gabarit = exactes[source]
            elif source:
                for cle, val in entrees:
                    if not cle.startswith("~"):
                        continue
                    sans_casse = cle.startswith("~*")
                    trouve = re.search(cle[2:] if sans_casse else cle[1:], source,
                                       re.IGNORECASE if sans_casse else 0)
                    if trouve:
                        gabarit, captures = val, trouve.groupdict()
                        break

            def recoller(m):
                nom_var = m.group(1) or m.group(2)
                if nom_var in captures:
                    return captures[nom_var]
                return variable_journal(arbre, "$" + nom_var, contexte)
            return re.sub(r"\$\{(\w+)\}|\$(\w+)", recoller, gabarit)
    raise AssertionError(f"{variable} : ni fournie, ni définie par une map du bloc http")


class JournalJetonMasqueTests(unittest.TestCase):
    """ADEP106 — le calendrier abonné de Tâches porte son jeton DANS l'adresse
    (`/api/django/taches/flux/<jeton>.ics`, imposé par l'iPhone). nginx ne passe pas
    par Django : son journal d'accès est masqué par `map` (les deux motifs de
    `CHEMINS_SENSIBLES`), son journal d'erreurs — qui écrit la requête et l'adresse de
    l'amont sans format réglable — est coupé sur le chemin du flux. Rejoué sur nginx
    1.27.5 (ancien et nouveau format côte à côte) : docs/audits/acceptation/ADEP/."""

    def setUp(self):
        self.arbre = analyser()

    def _requete(self, ligne):
        return variable_journal(self.arbre, "$requete_masquee", {"$request": ligne})

    def _referent(self, valeur):
        return variable_journal(self.arbre, "$referent_masque", {"$http_referer": valeur})

    def test_aucun_journal_d_acces_n_ecrit_l_adresse_brute(self):
        formats = {args[0]: "".join(a for a in args[1:] if not a.startswith("escape="))
                   for nom, args, _ in _toutes_les_directives(self.arbre) if nom == "log_format"}
        for nom_format, gabarit in formats.items():
            brutes = {v for v in re.findall(r"\$\{?(\w+)", gabarit)
                      if v in ADRESSES_BRUTES or v.startswith("arg_")}
            self.assertFalse(brutes, f"log_format {nom_format} écrit l'adresse telle quelle : "
                                     f"{sorted(brutes)}")
        journaux = [args for nom, args, _ in _toutes_les_directives(self.arbre)
                    if nom == "access_log"]
        self.assertTrue(journaux, "plus aucun access_log : nginx reprend `combined`, adresse brute")
        for args in journaux:
            if args != ["off"]:
                # sans nom de format, nginx écrit `combined` : `"$request"` brut.
                self.assertTrue(len(args) >= 2 and args[1] in formats, f"access_log {args}")
        taqinor = formats["taqinor"]
        self.assertIn('"$requete_masquee"', taqinor)
        self.assertIn('"$referent_masque"', taqinor)
        # YJPB2 — les durées qui servent au suivi des temps de réponse restent écrites.
        for champ in ("rt=$request_time", 'urt="$upstream_response_time"',
                      'uct="$upstream_connect_time"', 'us="$upstream_status"',
                      "rid=$upstream_http_x_request_id"):
            self.assertIn(champ, taqinor)

    def test_jeton_masque_dans_la_requete_et_le_referer(self):
        for recue, ecrite in LIGNES_A_SECRET:
            for champ, rendu in (("$request", self._requete(recue)),
                                 ("$http_referer", self._referent(recue))):
                self.assertEqual(rendu, ecrite, f"{champ} : {recue}")
                self.assertNotIn("EXEMPLE", rendu)
                self.assertNotIn("abc123", rendu)

    def test_toute_autre_ligne_sort_inchangee(self):
        for ligne in AUTRES_LIGNES:
            self.assertEqual(self._requete(ligne), ligne)
            self.assertEqual(self._referent(ligne), ligne)
        # variable absente : le tiret que nginx écrivait déjà (une map rendrait du vide).
        self.assertEqual(self._requete(""), "-")
        self.assertEqual(self._referent(""), "-")

    def test_meme_masquage_que_la_brique_django(self):
        """Jumeau de `apps/taches/auth_jeton.py::CHEMINS_SENSIBLES` : un motif changé côté
        Django sans son jumeau nginx rougit ici."""
        motifs, _ = motifs_django()
        self.assertEqual([nom for nom, _, _ in motifs], ["taches.flux", "taches.jeton"])
        for ligne in [recue for recue, _ in LIGNES_A_SECRET] + list(AUTRES_LIGNES):
            attendu = masque_django(ligne, occurrences=1)
            self.assertEqual(self._requete(ligne), attendu, ligne)
            self.assertEqual(self._referent(ligne), attendu, ligne)

    def test_flux_sans_journal_d_erreurs_memes_reglages_que_l_api(self):
        server = server_principal(self.arbre)
        motif, flux = location_pour(server, FLUX + "abc123.ics")
        self.assertEqual(motif, FLUX)
        # `^~` : la location à expression régulière du login admin (ASEC47) ne reprend
        # jamais ce préfixe, même pour `…/flux/<jeton>/login/`.
        self.assertIn(("^~", FLUX), [(mod, m) for mod, m, _ in locations(server)])
        self.assertEqual(location_pour(server, FLUX + "abc123/login/")[0], FLUX)
        directives = [(n, a) for n, a, _ in flux]
        # nginx écrit dans CHAQUE `error_log` déclaré : un second, à côté de /dev/null,
        # ressortirait la requête entière.
        self.assertEqual([a for n, a in directives if n == "error_log"], [["/dev/null"]])
        _, api = location_pour(server, "/api/django/crm/leads/")
        self.assertEqual([d for d in directives if d[0] != "error_log"],
                         [(n, a) for n, a, _ in api],
                         "le flux doit garder les réglages de /api/django/ (débit, délais, en-têtes)")
        entetes = entetes_effectifs(self.arbre, FLUX + "abc123.ics")
        self.assertIn("no-store", entetes.get("Cache-Control", ""))
        for nom in ENTETES_SECURITE:
            self.assertIn(nom, entetes)


if __name__ == "__main__":
    unittest.main()
