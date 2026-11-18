"""Tests ADEP103 (D-ADEP-103 = c) — l'origine ne croit l'IP transmise par un
nœud Cloudflare que si la requête porte le secret de relais du Worker.

Les plages Cloudflare de `trusted_proxies` (ADEP102) sont communes à TOUS les
comptes Cloudflare : sans secret, un Worker tiers forgeait `X-Forwarded-For`
(IP de preuve de signature, seaux de limite de débit). Garde statique des deux
moitiés, qui doivent parler le MÊME nom d'en-tête et de clé :
  * backend/caddy/Caddyfile + docker-compose.prod.yml (serveur) ;
  * apps/web/src/pages/api/_apiBase.ts (Worker), seule copie des en-têtes
    d'IP de tous les relais.
Le comportement réel (4 cas : sans clé / clé sans en-tête / mauvais secret /
bon secret) a été rejoué sur deux conteneurs caddy:2 — trace dans le DONE LOG.

ADEP106 (`CaddyJournalJetonTests`) : le journal de Caddy ne porte plus en clair
le jeton du calendrier abonné de Tâches (jumeau du masquage nginx, mêmes motifs
que la brique Django).

Stdlib pure (unittest). Run :
    python -m unittest scripts.tests.test_caddyfile_adep103_relais -v
"""
import re
import unittest
from pathlib import Path

from scripts.tests.test_nginx_cache_control import (
    AUTRES_LIGNES,
    FLUX,
    JETON_CAPTURE,
    JETON_FLUX,
    LIGNES_A_SECRET,
    masque_django,
)

RACINE = Path(__file__).resolve().parents[2]
CADDYFILE = RACINE / "backend" / "caddy" / "Caddyfile"
COMPOSE_PROD = RACINE / "docker-compose.prod.yml"
WEB = RACINE / "apps" / "web" / "src"
API_BASE = WEB / "pages" / "api" / "_apiBase.ts"

EN_TETE = "X-Taqinor-Relais"
CLE = "RELAIS_API_SECRET"


def _site_api(texte):
    m = re.search(r"^\{\$PUBLIC_HOSTNAME\}, api\.taqinor\.ma \{\n(.*?)^\}",
                  texte, re.S | re.M)
    if not m:
        raise AssertionError("site api.taqinor.ma introuvable dans le Caddyfile")
    return m.group(1)


class CaddyRelaisTests(unittest.TestCase):
    def setUp(self):
        self.texte = CADDYFILE.read_text(encoding="utf-8").replace("\r\n", "\n")
        self.site = _site_api(self.texte)

    def test_matcher_compare_l_en_tete_au_secret_seulement_si_cle_posee(self):
        m = re.search(r"^\s*@relais_non_prouve expression `(.+)`$",
                      self.site, re.M)
        self.assertIsNotNone(m, "matcher @relais_non_prouve absent")
        expr = m.group(1)
        # Sans clé : `"" != ""` est faux → rien ne change (D-ADEP-3).
        self.assertIn('"{$%s}" != ""' % CLE, expr)
        self.assertIn('{http.request.header.%s} != "{$%s}"' % (EN_TETE, CLE),
                      expr)

    def test_ip_transmise_retiree_sans_secret(self):
        for champ in ("X-Forwarded-For", "CF-Connecting-IP"):
            with self.subTest(champ=champ):
                self.assertRegex(
                    self.site,
                    r"(?m)^\s*request_header @relais_non_prouve -%s$"
                    % re.escape(champ))

    def test_le_secret_ne_sort_pas_de_caddy(self):
        proxy = re.search(r"reverse_proxy nginx:80 \{\n(.*?)\n\s*\}",
                          self.site, re.S)
        self.assertIsNotNone(proxy)
        self.assertRegex(proxy.group(1),
                         r"(?m)^\s*header_up -%s$" % re.escape(EN_TETE))

    def test_plages_cloudflare_toujours_de_confiance(self):
        # ADEP102 (jumeau) : sans elles, le relais légitime perdrait l'IP du
        # visiteur ; le secret ne fait que trier les nœuds Cloudflare.
        self.assertRegex(self.texte,
                         r"trusted_proxies static [^\n]*173\.245\.48\.0/20")

    def test_compose_prod_passe_la_cle_a_caddy_avec_defaut_vide(self):
        compose = COMPOSE_PROD.read_text(encoding="utf-8")
        caddy = re.search(r"^  caddy:\n(.*?)^  \S", compose, re.S | re.M)
        self.assertIsNotNone(caddy)
        self.assertRegex(caddy.group(1),
                         r"(?m)^\s+%s: \$\{%s:-\}$" % (CLE, CLE))


def _bloc(texte, ouvrante):
    """Texte entre l'accolade ouvrante d'indice `ouvrante` et sa fermante. Les
    chaînes (accents graves, guillemets) et les commentaires sont sautés : une
    expression régulière porte des accolades."""
    assert texte[ouvrante] == "{"
    profondeur, i = 0, ouvrante
    while i < len(texte):
        c = texte[i]
        if c in "`\"":
            i = texte.index(c, i + 1)
        elif c == "#" and (i == 0 or texte[i - 1] in " \t\n"):
            i = texte.index("\n", i)
            continue
        elif c == "{":
            profondeur += 1
        elif c == "}":
            profondeur -= 1
            if profondeur == 0:
                return texte[ouvrante + 1:i]
        i += 1
    raise AssertionError("accolade non refermée dans le Caddyfile")


def _sous_bloc(texte, entete):
    """Corps du bloc dont la ligne d'ouverture est `<entete> {` (None s'il manque)."""
    m = re.search(r"(?m)^[ \t]*%s \{$" % re.escape(entete), texte)
    return _bloc(texte, m.end() - 1) if m else None


class CaddyJournalJetonTests(unittest.TestCase):
    """ADEP106 — Caddy n'écrit aucun journal d'accès, mais son journal d'ERREURS
    (`http.log.error`) écrit la requête entière dès que nginx ne répond pas (à
    chaque déploiement) : l'adresse `/api/django/taches/flux/<jeton>.ics` et le
    `Referer` y sortaient en clair. Le bloc `log` des options globales garde la
    sortie et le format par défaut et remplace seulement les deux secrets que
    Django masque déjà. Rejoué sur caddy 2.7.6 → 2.11.9 (validate, reload, ligne
    réelle) : docs/audits/acceptation/ADEP/."""

    CHAMPS = ("request>uri", "request>headers>Referer")

    def setUp(self):
        self.texte = CADDYFILE.read_text(encoding="utf-8").replace("\r\n", "\n")
        ouverture = re.search(r"(?m)^\{$", self.texte)
        self.assertIsNotNone(ouverture, "bloc d'options globales introuvable")
        self.options = _bloc(self.texte, ouverture.start())
        self.journal = _sous_bloc(self.options, "log")
        self.assertIsNotNone(self.journal, "bloc `log` absent des options globales")
        self.filtre = _sous_bloc(self.journal, "format filter")
        self.assertIsNotNone(self.filtre, "`format filter` absent du bloc `log`")
        champs = _sous_bloc(self.filtre, "fields")
        self.assertIsNotNone(champs, "`fields` absent de `format filter`")
        self.filtres = {champ: (motif, remplacement) for champ, motif, remplacement
                        in re.findall(r"(?m)^[ \t]*(\S+) regexp `([^`]*)` `([^`]*)`$", champs)}

    def _masquer(self, champ, valeur):
        """Le filtre `regexp` de Caddy (Go `ReplaceAllString` : toutes les
        occurrences, `${n}` = groupe n) rejoué en Python."""
        motif, remplacement = self.filtres[champ]
        return re.sub(motif, re.sub(r"\$\{(\w+)\}", r"\\g<\1>", remplacement), valeur)

    def test_l_adresse_et_le_referer_sont_filtres_par_le_meme_motif(self):
        self.assertEqual(set(self.filtres), set(self.CHAMPS))
        self.assertEqual(len(set(self.filtres.values())), 1)

    def test_le_journal_garde_sa_sortie_et_son_format(self):
        # JSON sur la sortie d'erreur, niveau INFO : rien d'autre n'est réglé.
        self.assertRegex(self.filtre, r"(?m)^[ \t]*wrap json$")
        hors_filtre = self.journal.replace(self.filtre, "")
        self.assertEqual(re.findall(r"(?m)^[ \t]*(\w+)", hors_filtre), ["format"],
                         "le bloc `log` ne règle que le format (ni output, ni level)")

    def test_aucun_site_n_ouvre_un_journal_sans_filtre(self):
        # Un `log` dans un site ouvrirait un journal d'ACCÈS à part, hors du filtre.
        sites = self.texte.split(self.options, 1)[1]
        self.assertNotRegex(sites, r"(?m)^[ \t]*log(_\w+)?([ \t]|$)")

    def test_jeton_masque_dans_l_adresse_et_le_referer(self):
        for champ in self.CHAMPS:
            self.assertEqual(self._masquer(champ, FLUX + "abc123.ics"), FLUX + "<jeton>.ics")
            for recue, ecrite in LIGNES_A_SECRET:
                rendu = self._masquer(champ, recue)
                self.assertEqual(rendu, ecrite, f"{champ} : {recue}")
                self.assertNotIn("EXEMPLE", rendu)
            for ligne in AUTRES_LIGNES:
                self.assertEqual(self._masquer(champ, ligne), ligne)

    def test_meme_masquage_que_la_brique_django(self):
        """Jumeau de `apps/taches/auth_jeton.py::CHEMINS_SENSIBLES` (toutes les
        occurrences, comme `core.chemins_sensibles.masquer`)."""
        plusieurs = (f"{FLUX}{JETON_FLUX}.ics?retour=%2Ftaches%2Fflux%2F{JETON_FLUX}.ics"
                     f"&a={JETON_CAPTURE},{JETON_CAPTURE}")
        self.assertEqual(masque_django(plusieurs),
                         f"{FLUX}<jeton>.ics?retour=%2Ftaches%2Fflux%2F<jeton>.ics"
                         "&a=tqc_<jeton>,tqc_<jeton>")
        for ligne in [recue for recue, _ in LIGNES_A_SECRET] + list(AUTRES_LIGNES) + [plusieurs]:
            for champ in self.CHAMPS:
                self.assertEqual(self._masquer(champ, ligne), masque_django(ligne), ligne)


class WorkerRelaisTests(unittest.TestCase):
    def test_le_worker_envoie_le_meme_en_tete_depuis_la_meme_cle(self):
        source = API_BASE.read_text(encoding="utf-8")
        self.assertIn("export function entetesIpVisiteur(", source)
        self.assertIn("'%s': secret" % EN_TETE, source)
        self.assertIn(".%s?.trim()" % CLE, source)

    def test_aucun_relais_ne_pose_l_ip_hors_de_la_copie_unique(self):
        """Un nouveau relais qui écrirait `'X-Forwarded-For': ip` à la main
        enverrait l'IP SANS le secret : l'origine la retirerait en silence."""
        fautifs = []
        for chemin in sorted(WEB.rglob("*")):
            if chemin.suffix not in (".ts", ".astro") or chemin == API_BASE \
                    or chemin.name.endswith(".test.ts"):
                continue
            texte = chemin.read_text(encoding="utf-8")
            if re.search(r"""['"]X-Forwarded-For['"]\s*:""", texte):
                fautifs.append(str(chemin.relative_to(RACINE)))
        self.assertEqual(fautifs, [])


if __name__ == "__main__":
    unittest.main()
