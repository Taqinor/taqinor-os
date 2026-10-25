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

Stdlib pure (unittest). Run :
    python -m unittest scripts.tests.test_caddyfile_adep103_relais -v
"""
import re
import unittest
from pathlib import Path

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
