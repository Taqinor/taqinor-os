"""QJR162 — trois replis silencieux du renderer premium lèvent au lieu de
fabriquer.

(a) ``_proposition_link`` : ``href = url if url.startswith("http") else
    "https://" + url``, avec pour seul contrôle ``"/proposition/" not in url``.
    ``settings.SITE_URL`` fait ``os.environ.get('SITE_URL', …)`` : une variable
    d'environnement PRÉSENTE MAIS VIDE donne ``""`` → lien relatif → QR imprimé
    « https:///proposition/… », MORT chez le client. Le dépôt s'en protège déjà
    pour ``PUBLIC_SITE_URL``, pas pour ``SITE_URL``, alors que la docstring de
    la fonction promet d'omettre la vignette « plutôt que de porter un QR qui
    mène à un 404 ».
(b) ``data.get("all_items", [])`` : défaut SILENCIEUX à liste vide alors que le
    même appel exige ``data["sans_items"]`` en dur — une charge utile privée
    d'``all_items`` mais porteuse de ``totaux_all`` produisait un tableau
    d'équipements VIDE sous un Total TTC complet.
(c) ``_fallback_totaux`` recalculait la chaîne avec un taux de TVA UNIQUE et
    SANS ``tva_par_taux``, et son ``or`` mordait aussi sur un dict vide : sur un
    devis à taux mixtes, la colonne affichait 10 % et 20 % par ligne et le bloc
    une seule ligne « TVA (20 %) ». ``page_onepage`` recalculait localement avec
    le même défaut.

Run (sans base de données) :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr162_replis_renderer -v 2
"""
from django.test import SimpleTestCase

from apps.ventes.quote_engine import generate_devis_premium as moteur
from apps.ventes.tests import _moteur_fixtures as F


class TestRepliA_LienDeProposition(SimpleTestCase):
    """(a) — pas d'URL fabriquée : un lien sans hôte s'OMET."""

    def setUp(self):
        self._links = getattr(moteur, "LINKS", None)

    def tearDown(self):
        if self._links is None:
            if hasattr(moteur, "LINKS"):
                delattr(moteur, "LINKS")
        else:
            moteur.LINKS = self._links

    def _lien(self, signer):
        moteur.LINKS = {"signer": signer}
        return moteur._proposition_link()

    def test_url_absolue_rendue_telle_quelle(self):
        href, court = self._lien(
            "https://taqinor.ma/proposition/karim/abc123")
        self.assertEqual(href, "https://taqinor.ma/proposition/karim/abc123")
        self.assertEqual(court, "taqinor.ma/proposition")

    def test_site_url_vide_omet_la_vignette(self):
        """Le cas EXACT du constat : SITE_URL présent mais vide."""
        self.assertEqual(self._lien("/proposition/karim/abc123"), ("", ""))

    def test_schema_manquant_omet_la_vignette(self):
        self.assertEqual(self._lien("taqinor.ma/proposition/k/abc"), ("", ""))

    def test_hote_vide_omet_la_vignette(self):
        self.assertEqual(self._lien("https:///proposition/karim/abc"),
                         ("", ""))

    def test_aucun_qr_mort_n_est_jamais_compose(self):
        for mauvais in ("", "   ", "/proposition/", "https:///proposition/x",
                        "ftp://taqinor.ma/proposition/x"):
            with self.subTest(url=mauvais):
                self.assertEqual(self._lien(mauvais), ("", ""))


class TestRepliB_AllItems(SimpleTestCase):
    """(b) — accès DUR : une charge utile sans ``all_items`` ne se rend pas."""

    def test_all_items_manquant_leve(self):
        data = F.donnees_legacy(pdf_mode="onepage")
        data.pop("all_items", None)
        with self.assertRaises(KeyError):
            moteur.render_html_for(data)

    def test_all_items_present_rend_ses_lignes(self):
        data = F.donnees_legacy(pdf_mode="onepage")
        data["totaux_all"] = data["totaux_sans"]
        html = moteur.render_html_for(data)
        self.assertIn(data["all_items"][0]["designation"], html)


class TestRepliC_TotauxCanoniques(SimpleTestCase):
    """(c) — jamais de chaîne de totaux fabriquée à taux unique."""

    def test_totaux_sans_manquants_levent(self):
        data = F.donnees_legacy(pdf_mode="full")
        data.pop("totaux_sans", None)
        with self.assertRaises(ValueError) as ctx:
            moteur.render_html_for(data)
        self.assertIn("totaux canoniques manquants", str(ctx.exception))

    def test_dict_vide_leve_aussi(self):
        """L'ancien ``or`` mordait sur un dict VIDE et fabriquait la chaîne."""
        data = F.donnees_legacy(pdf_mode="full")
        data["totaux_avec"] = {}
        with self.assertRaises(ValueError):
            moteur.render_html_for(data)

    def test_le_une_page_leve_sans_totaux_all(self):
        data = F.donnees_legacy(pdf_mode="onepage")
        data.pop("totaux_all", None)
        with self.assertRaises(ValueError) as ctx:
            moteur.render_html_for(data)
        self.assertIn("totaux_all", str(ctx.exception))

    def test_le_multi_taux_garde_ses_lignes_par_taux(self):
        """Avec les totaux canoniques, la TVA reste éclatée par taux."""
        data = F.donnees_legacy(pdf_mode="onepage")
        data["totaux_all"] = {
            "ht_brut": 48120.75, "remise": 0.0, "ht_net": 48120.75,
            "tva": 7123.46, "ttc": 55244.21,
            "tva_par_taux": [{"taux": 10, "montant": 2145.83},
                             {"taux": 20, "montant": 4977.63}],
        }
        html = moteur.render_html_for(data)
        self.assertIn("TVA (10", html)
        self.assertIn("TVA (20", html)

    def test_le_rendu_nominal_reste_intact(self):
        data = F.donnees_legacy(pdf_mode="full")
        html = moteur.render_html_for(data)
        self.assertIn("Sous-total HT", html)
        self.assertEqual(html.count('class="page"'), 3)
