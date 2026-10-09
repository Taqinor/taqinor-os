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
"""
import re
import unittest
from pathlib import Path

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

    def test_aucun_no_store_litteral_au_niveau_server(self):
        server = server_principal(self.arbre)
        for nom, args, _ in server:
            if nom == "add_header" and args[0].lower() == "cache-control":
                self.assertTrue(args[1].startswith("$"),
                                "Cache-Control littéral au niveau server : hérité par /")


if __name__ == "__main__":
    unittest.main()
