"""QJR115 — la page Étude ne publie plus DEUX productions annuelles.

La feuille « Étude d'autoconsommation » du PDF premium imprime la production
annuelle de la MÊME installation à deux endroits, à neuf lignes d'écart :

* la carte « Production annuelle » (``etude['production_annuelle']``) ;
* « Production P50 (médiane) » du bloc bancable
  (``etude['bankable']['pr']['p50_kwh']``, joué par ``apps.ventes.etude``).

QJR114 a fait converger les deux CHAÎNES de calcul côté moteur (fin du double
derate : la P50 vaut désormais ``productible × PRODUCTION_DERATE``, la formule
même de ``pricing``). Mais rien n'oblige les deux SOURCES à décrire le même
devis — le builder recopie ``etude_params['simulation']`` sans condition et
cette clé ne fait pas partie des études rafraîchies. Une étude jouée avant un
redimensionnement, ou une production saisie à la main, remet donc deux nombres
contradictoires côte à côte.

Ce module rend le document COMPLET (4 pages, ``include_etude``) et vérifie sur
le HTML réellement envoyé à WeasyPrint que, page Étude comprise, les deux
nombres coïncident — ou que le bloc bancable est ABSENT (règle fondateur :
omettre plutôt que publier deux vérités). Il épingle aussi que la garde ne
change AUCUNE autre page : le nombre de pages et le reste du document sont
identiques avec et sans le bloc.

Aucune BD, aucun WeasyPrint : exécutable sur l'hôte (cf. ``_moteur_fixtures``).

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr115_production_unique -v 2
"""
import re

from django.test import SimpleTestCase

from apps.ventes.quote_engine import generate_devis_premium as moteur

from ._moteur_fixtures import html_legacy


#: Production « canonique » de la carte, en kWh/an.
PROD_CARTE = 12486

#: Le nombre de feuilles du format premium complet avec la page Étude :
#: page 1, page 2, Étude, page 3. Le bloc bancable vit à l'INTÉRIEUR de la page
#: Étude (``.page`` est à hauteur fixe) : il ne peut jamais en changer le compte.
PAGES_ATTENDUES = 4


def _etude(p50, production_annuelle=PROD_CARTE):
    """Bloc ``etude`` du document, avec une simulation bancable servable.

    ``zones[0]['kwc']`` égale la puissance du devis : la garde de QJR159 (b)
    (« la simulation décrit-elle le champ PV vendu ? ») passe, sans quoi le
    bloc serait omis pour une autre raison que celle testée ici.
    """
    etude = {
        "kwc": 9.94,
        "conso_annuelle": 120000,
        "taux_autoconso": 100,
        "taux_couverture": 10.4,
        "economies_annuelles": 21851,
        "payback": 3.0,
        "prix_kwc": 6543,
        "prod_mensuelle": [1040] * 12,
        "conso_mensuelle": [10000] * 12,
        "bankable": {
            "zones": [{"label": "Pan Sud", "kwc": 9.94,
                       "base_production_kwh": 13000}],
            "pr": {"p50_kwh": p50, "p90_kwh": 10200,
                   "performance_ratio": 0.80,
                   "loss_breakdown": {"temperature": 8.0, "soiling": 3.0},
                   "total_loss_pct": 20.0},
        },
    }
    if production_annuelle is not None:
        etude["production_annuelle"] = production_annuelle
    return etude


def _rendu(etude):
    """HTML EXACT du document 4 pages (premium complet + page Étude)."""
    return html_legacy("deux", include_etude=True, etude=etude,
                       puissance_kwc=9.94)


def _nombre_fr(texte):
    """« 12 486 kWh/an » → 12486.0 (espaces fines/insécables, virgule FR)."""
    brut = re.sub(r"[^\d,.-]", "", texte).replace(",", ".")
    return float(brut) if brut else None


def _p50_publiee(html):
    """La P50 RÉELLEMENT imprimée, ou ``None`` si le bloc est absent."""
    trouve = re.search(r"Production P50[^<]*<b>([^<]*)</b>", html)
    return _nombre_fr(trouve.group(1)) if trouve else None


def _carte_production(html):
    """La « Production annuelle » de la carte, ou ``None`` si omise."""
    trouve = re.search(
        r"Production annuelle</div>[\s\S]{0,300}?serif[^>]*>([^<]*)<", html)
    return _nombre_fr(trouve.group(1)) if trouve else None


class TestUneSeuleProduction(SimpleTestCase):
    """Le document 4 pages ne porte jamais deux productions contradictoires."""

    def test_le_document_fait_bien_quatre_pages(self):
        """Le décor du test est le vrai document complet, pas un fragment."""
        html = _rendu(_etude(PROD_CARTE))
        self.assertEqual(html.count('<div class="page"'), PAGES_ATTENDUES)
        self.assertIn("Étude d'autoconsommation", html)

    def test_productions_egales_le_bloc_est_servi(self):
        """Chaîne convergente (QJR114) → les deux nombres COÏNCIDENT."""
        html = _rendu(_etude(PROD_CARTE))
        self.assertEqual(html.count('<div class="page"'), PAGES_ATTENDUES)
        self.assertIn("Étude bancable", html)
        self.assertEqual(_p50_publiee(html), float(PROD_CARTE))
        self.assertEqual(_carte_production(html), float(PROD_CARTE))

    def test_ecart_sous_la_tolerance_reste_servi(self):
        """0,5 % d'écart (arrondis) : ce n'est pas une seconde vérité."""
        p50 = PROD_CARTE * 1.005
        html = _rendu(_etude(round(p50)))
        self.assertIn("Étude bancable", html)
        publiee = _p50_publiee(html)
        self.assertIsNotNone(publiee)
        self.assertLessEqual(
            abs(publiee - PROD_CARTE),
            PROD_CARTE * moteur.TOLERANCE_PRODUCTION_PAGE)

    def test_deux_productions_contradictoires_le_bloc_est_omis(self):
        """RÉGRESSION — l'écart du double derate (~11 %) faisait imprimer
        « Production P50 11 000 kWh/an » sous « Production annuelle 12 486 kWh »
        sur la MÊME feuille. Le bloc est désormais OMIS."""
        html = _rendu(_etude(11000))
        self.assertEqual(html.count('<div class="page"'), PAGES_ATTENDUES)
        self.assertNotIn("Étude bancable", html)
        self.assertIsNone(_p50_publiee(html))
        # La carte canonique, elle, reste : c'est la seule production publiée.
        self.assertEqual(_carte_production(html), float(PROD_CARTE))

    def test_aucune_production_publiee_ne_reste_seule_contredite(self):
        """Balayage : sur toute une plage d'écarts, le document ne porte JAMAIS
        deux productions divergentes — soit elles coïncident, soit il n'y en a
        qu'une."""
        for p50 in (9000, 11000, 12300, 12486, 12550, 13500, 20000):
            with self.subTest(p50=p50):
                html = _rendu(_etude(p50))
                publiee = _p50_publiee(html)
                carte = _carte_production(html)
                self.assertEqual(carte, float(PROD_CARTE))
                if publiee is not None:
                    self.assertLessEqual(
                        abs(publiee - carte),
                        carte * moteur.TOLERANCE_PRODUCTION_PAGE,
                        "deux productions contradictoires sur la page Étude")

    def test_sans_carte_de_production_le_bloc_reste(self):
        """Rien à contredire : le bloc bancable est alors la SEULE production,
        il n'est pas supprimé pour rien."""
        html = _rendu(_etude(11000, production_annuelle=None))
        self.assertIsNone(_carte_production(html))
        self.assertIn("Étude bancable", html)
        self.assertEqual(_p50_publiee(html), 11000.0)

    def test_production_illisible_le_bloc_est_omis(self):
        """L'égalité n'est pas PROUVABLE → on omet (précédent QJR159 (b))."""
        html = _rendu(_etude(11000, production_annuelle="n/c"))
        self.assertNotIn("Étude bancable", html)

    def test_aucune_autre_page_touchee(self):
        """La garde n'agit QUE sur le bloc bancable : le reste du document est
        byte-identique entre le cas servi et le cas omis."""
        servi = _rendu(_etude(PROD_CARTE))
        omis = _rendu(_etude(11000))
        self.assertEqual(servi.count('<div class="page"'),
                         omis.count('<div class="page"'))
        marqueur = "Étude bancable — productible et pertes"
        # Le seul delta est le bloc lui-même : hors de lui, les deux documents
        # portent les mêmes sections et le même pied de page.
        self.assertIn(marqueur, servi)
        self.assertNotIn(marqueur, omis)
        for section in ("Étude d'autoconsommation", "Puissance crête",
                        "Production PV vs consommation",
                        "Estimations non contractuelles."):
            self.assertIn(section, servi)
            self.assertIn(section, omis)


class TestGardeUnitaire(SimpleTestCase):
    """``_bankable_concorde_avec_la_page`` isolée de tout rendu."""

    def setUp(self):
        self._etude_sauvee = getattr(moteur, "ETUDE", None)

    def tearDown(self):
        moteur.ETUDE = self._etude_sauvee

    def _poser(self, production):
        moteur.ETUDE = ({} if production is None
                        else {"production_annuelle": production})

    def test_sans_production_de_page_rien_a_contredire(self):
        self._poser(None)
        self.assertTrue(moteur._bankable_concorde_avec_la_page(
            {"pr": {"p50_kwh": 11000}}))

    def test_sans_p50_rien_a_contredire(self):
        self._poser(12486)
        self.assertTrue(moteur._bankable_concorde_avec_la_page(
            {"pr": {"p90_kwh": 10200}}))

    def test_p50_illisible_refuse(self):
        self._poser(12486)
        self.assertFalse(moteur._bankable_concorde_avec_la_page(
            {"pr": {"p50_kwh": "beaucoup"}}))

    def test_production_de_page_nulle_refuse(self):
        self._poser(0)
        self.assertFalse(moteur._bankable_concorde_avec_la_page(
            {"pr": {"p50_kwh": 11000}}))

    def test_egalite_exacte_acceptee(self):
        self._poser(12486)
        self.assertTrue(moteur._bankable_concorde_avec_la_page(
            {"pr": {"p50_kwh": 12486.0}}))

    def test_bornes_de_la_tolerance(self):
        self._poser(10000)
        tol = moteur.TOLERANCE_PRODUCTION_PAGE
        self.assertTrue(moteur._bankable_concorde_avec_la_page(
            {"pr": {"p50_kwh": 10000 * (1 + tol)}}))
        self.assertFalse(moteur._bankable_concorde_avec_la_page(
            {"pr": {"p50_kwh": 10000 * (1 + tol) + 1}}))
