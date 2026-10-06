"""CIQ309 — bloc client entreprise sur les PDF C&I : raison sociale, ICE,
RC, IF, interlocuteur et fonction, chaque champ omis s'il est vide.

Rendu RÉEL des deux gabarits (``render.build_html`` sur ``_augment``) à
partir de la charge utile servie par le builder (``entreprise_client``),
passée par ``echapper_textes_client`` comme en production (un seul
échappement, QJR30). Le bloc tient dans la couverture existante : 3 et 4
pages (WeasyPrint, ``@tag('weasyprint')``).
"""
import copy
from types import SimpleNamespace

from django.test import SimpleTestCase, tag

from apps.ventes.quote_engine.builder import (
    echapper_textes_client, entreprise_client_du_client,
)
from apps.ventes.quote_engine.ci.synthese import synthese_ci
from apps.ventes.quote_engine.commercial import render as c_render
from apps.ventes.quote_engine.commercial import renderer as c_renderer
from apps.ventes.quote_engine.commercial import sample_data as c_sample
from apps.ventes.quote_engine.industriel import render as i_render
from apps.ventes.quote_engine.industriel import renderer as i_renderer
from apps.ventes.quote_engine.industriel import sample_data as i_sample

GABARITS = (
    ("commercial", c_sample, c_renderer, c_render, 3),
    ("industriel", i_sample, i_renderer, i_render, 4),
)


def _client(**champs):
    base = dict(type_client="entreprise", nom="Atlas Froid & Fils SARL",
                prenom=None, ice="001234567000089", rc="RC 45 871",
                if_fiscal="40112233", adresse="Zone industrielle, Fès",
                adresse_siege="12 bd Zerktouni, Casablanca",
                contact_nom="Karim Benali", contact_fonction="Directeur")
    base.update(champs)
    return SimpleNamespace(**base)


def _rendu(sample, renderer, render, client):
    data = copy.deepcopy(sample.build())
    entreprise = entreprise_client_du_client(client)
    if entreprise is not None:
        data["entreprise_client"] = entreprise
    data["client_name"] = data["client_full"] = client.nom
    d = renderer._augment(echapper_textes_client(data))
    return d, render.build_html(d)


def _page1(html, prefixe):
    """Le HTML de la COUVERTURE seule (jusqu'à la racine de la page 2)."""
    debut = html.index(f'class="{prefixe}-root"')
    suivante = "c2-root" if prefixe == "c1c" else "i2-root"
    return html[debut:html.index(f'class="{suivante}"')]


class BlocClientEntreprise(SimpleTestCase):

    def test_client_complet_cinq_champs_en_page_1(self):
        for nom, sample, renderer, render, _pages in GABARITS:
            with self.subTest(gabarit=nom):
                _d, html = _rendu(sample, renderer, render, _client())
                page1 = _page1(html, "c1c" if nom == "commercial" else "i1")
                bloc = page1[page1.index('-ent"'):]
                bloc = bloc[:bloc.index("</div>")]
                self.assertIn("ICE&#160;: 001234567000089", bloc)
                self.assertIn("RC&#160;: RC 45 871", bloc)
                self.assertIn("IF&#160;: 40112233", bloc)
                self.assertIn("Siège&#160;: 12 bd Zerktouni, Casablanca",
                              bloc)
                self.assertIn("À l'attention de Karim Benali, Directeur",
                              bloc)
                # La raison sociale est le nom en gras de la couverture.
                self.assertIn("Atlas Froid &amp; Fils", page1)

    def test_raison_sociale_differente_du_nom_imprimee(self):
        client = _client()
        data = copy.deepcopy(i_sample.build())
        data["entreprise_client"] = entreprise_client_du_client(client)
        data["client_name"] = data["client_full"] = "Karim Benali"
        html = i_render.build_html(i_renderer._augment(
            echapper_textes_client(data)))
        self.assertIn("Raison sociale&#160;: Atlas Froid &amp; Fils SARL",
                      html)

    def test_client_sans_ice_aucun_libelle_ice(self):
        for nom, sample, renderer, render, _pages in GABARITS:
            with self.subTest(gabarit=nom):
                _d, html = _rendu(sample, renderer, render,
                                  _client(ice="", rc="", if_fiscal=""))
                # La COUVERTURE (bloc client) : la case « Bon pour accord »
                # de la dernière page (CIQ320) garde sa ligne « ICE » à
                # remplir, qui n'est pas une donnée du client.
                html = html.split('class="page"')[1]
                self.assertNotIn("ICE&#160;:", html)
                self.assertNotIn("RC&#160;:", html)
                self.assertNotIn("IF&#160;:", html)
                self.assertNotIn("—&#160;", html)

    def test_texte_client_echappe_une_seule_fois(self):
        for nom, sample, renderer, render, _pages in GABARITS:
            with self.subTest(gabarit=nom):
                _d, html = _rendu(sample, renderer, render, _client(
                    contact_nom="Karim <B> & Co", adresse_siege=""))
                self.assertIn("Karim &lt;B&gt; &amp; Co", html)
                self.assertNotIn("&amp;amp;", html)
                self.assertNotIn("&amp;lt;", html)

    def test_particulier_sans_identifiant_aucun_bloc(self):
        client = _client(type_client="particulier", ice="", rc="",
                         if_fiscal="")
        self.assertIsNone(entreprise_client_du_client(client))
        for nom, sample, renderer, render, _pages in GABARITS:
            with self.subTest(gabarit=nom):
                _d, html = _rendu(sample, renderer, render, client)
                self.assertNotIn('-ent"', html)

    def test_siege_identique_au_site_omis(self):
        ent = entreprise_client_du_client(
            _client(adresse_siege="Zone industrielle, Fès"))
        self.assertEqual(ent["siege"], "")

    def test_synthese_ci_recopie_le_bloc(self):
        data = copy.deepcopy(c_sample.build())
        data["entreprise_client"] = entreprise_client_du_client(_client())
        self.assertEqual(synthese_ci(data)["entreprise_client"],
                         data["entreprise_client"])
        data.pop("entreprise_client")
        self.assertNotIn("entreprise_client", synthese_ci(data))

    def test_aucune_donnee_de_marge(self):
        ent = entreprise_client_du_client(_client(prix_achat=123))
        self.assertEqual(set(ent), {"raison_sociale", "ice", "rc",
                                    "if_fiscal", "siege", "interlocuteur",
                                    "fonction"})


@tag("weasyprint")
class BlocClientEntreprisePages(SimpleTestCase):

    def test_pages_tenues(self):
        try:
            from weasyprint import HTML
        except Exception:  # pragma: no cover - libs natives absentes
            self.skipTest("weasyprint indisponible")
        for nom, sample, renderer, render, pages in GABARITS:
            with self.subTest(gabarit=nom):
                _d, html = _rendu(sample, renderer, render, _client())
                self.assertEqual(len(HTML(string=html).render().pages),
                                 pages)
