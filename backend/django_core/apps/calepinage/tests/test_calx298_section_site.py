"""CALX298 — la section « Site et source météo » du rapport.

Ce qui est prouvé ici, sur le résultat du CONTRAT
(``contract_samples/calepinage_resultat.json``, CALX70) :

* une base d'irradiance ``{'source': None}`` imprime « source non
  renseignée » et AUCUN nom de fournisseur (ni « PVGIS », ni tout autre) ;
* l'absence de profil d'horizon (``meteo.horizon`` absent, ou
  ``origine: 'aucun'``) imprime le MOTIF de repli — jamais un horizon plat
  (aucune mention « 0° ») ;
* un profil d'horizon PUBLIÉ imprime son origine et sa hauteur maximale ;
* la fenêtre d'années imprimée est EXACTEMENT celle du résultat
  (``production.base.fenetre_annees``), jamais recalculée depuis
  ``meteo.annees`` — un jeu d'années incohérent avec la fenêtre le prouve ;
* l'altitude publiée par le résultat (``meteo.point.altitude_m``) est
  imprimée avec la source « PVGIS » ; absente, « source non renseignée »,
  jamais un mètre inventé ;
* le fuseau publié (``meteo.heure.fuseau_site``) est imprimé avec sa source
  (celle que ``services/site.py::fuseau_du_site`` republie, jamais une
  source inventée dans ce module) ;
* ville, adresse, coordonnées et source du repère viennent de
  ``contexte['site']`` (CAL15), jamais du résultat du moteur ;
* dans le rapport assemblé, la section passe par ce rédacteur et sa feuille
  est posée dans le ``<head>``.

Run :
    cd backend/django_core
    python -m pytest apps/calepinage/tests/test_calx298_section_site.py -q
"""
import copy
import json
import pathlib
import re
import unittest
from html import escape
from types import SimpleNamespace

from apps.calepinage.services.rapport import (
    construire_rapport, html_de_rapport,
)
from apps.calepinage.services.rapport.site import (
    MENTION_HORIZON_ABSENT, html_de_section,
)

RACINE_APP = pathlib.Path(__file__).resolve().parents[1]


def _charger(nom):
    return json.loads((RACINE_APP / 'contract_samples' / nom)
                      .read_text(encoding='utf-8'))


RESULTAT = _charger('calepinage_resultat.json')['exemple']
MOTIF = ("Aucune base d'irradiance publiée pour ce calepinage : lancez la "
         "simulation (onglet Production) pour que la source météo soit "
         "connue.")


def contexte(resultat, site=None, langue='fr'):
    return {'resultat': resultat, 'site': site or {}, 'langue': langue,
            'section': {'code': 'site_meteo', 'motif_si_absent': MOTIF}}


def resultat_de_base():
    return copy.deepcopy(RESULTAT)


class SourceDIrradianceTest(unittest.TestCase):
    def test_une_source_absente_dit_non_renseignee_sans_nom_de_fournisseur(
            self):
        resultat = resultat_de_base()
        resultat['production']['base']['source'] = None
        html = html_de_section(contexte(resultat))
        ligne = re.search(r"<tr><th>Base d&#x27;irradiance</th>.*?</tr>",
                          html).group(0)
        self.assertIn('source non renseignée', ligne)
        self.assertNotIn('PVGIS', ligne)
        self.assertNotIn('pvgis', ligne)

    def test_une_source_connue_est_traduite(self):
        html = html_de_section(contexte(resultat_de_base()))
        self.assertIn('PVGIS', html)


class HorizonTest(unittest.TestCase):
    def test_absence_de_profil_imprime_le_motif_pas_un_horizon_plat(self):
        resultat = resultat_de_base()
        resultat['meteo']['horizon'] = {
            'origine': 'aucun', 'hauteur_max_deg': None, 'base_horizon': None}
        html = html_de_section(contexte(resultat))
        self.assertIn(escape(MENTION_HORIZON_ABSENT), html)
        self.assertNotIn('0°', html)
        self.assertNotIn("Profil d&#x27;horizon", html)

    def test_meteo_sans_cle_horizon_imprime_aussi_le_motif(self):
        resultat = resultat_de_base()
        del resultat['meteo']['horizon']
        html = html_de_section(contexte(resultat))
        self.assertIn(escape(MENTION_HORIZON_ABSENT), html)

    def test_un_profil_publie_imprime_son_origine_et_sa_hauteur(self):
        html = html_de_section(contexte(resultat_de_base()))
        self.assertIn("Profil d&#x27;horizon", html)
        self.assertIn('dem_pvgis', html)
        self.assertIn('hauteur maximale 8,5°', html)
        self.assertNotIn(escape(MENTION_HORIZON_ABSENT), html)


class FenetreDAnneesTest(unittest.TestCase):
    def test_la_fenetre_imprimee_est_celle_du_resultat_non_recalculee(self):
        resultat = resultat_de_base()
        resultat['production']['base']['fenetre_annees'] = '2020-2021'
        # Un jeu d'années DÉLIBÉRÉMENT incohérent : si le rédacteur le
        # recalculait, la fenêtre imprimée changerait.
        resultat['meteo']['annees'] = [1999]
        html = html_de_section(contexte(resultat))
        self.assertIn('2020-2021', html)
        self.assertNotIn('1999', html)


class AltitudeEtFuseauTest(unittest.TestCase):
    def test_altitude_publiee_porte_la_source_pvgis(self):
        html = html_de_section(contexte(resultat_de_base()))
        ligne = re.search(r'<tr><th>Altitude</th>.*?</tr>', html).group(0)
        self.assertIn('50', ligne)
        self.assertIn('PVGIS', ligne)

    def test_altitude_absente_dit_source_non_renseignee_jamais_un_metre(
            self):
        resultat = resultat_de_base()
        resultat['meteo']['point']['altitude_m'] = None
        html = html_de_section(contexte(resultat))
        ligne = re.search(r'<tr><th>Altitude</th>.*?</tr>', html).group(0)
        self.assertIn('—', ligne)
        self.assertIn('source non renseignée', ligne)

    def test_fuseau_publie_porte_sa_source(self):
        html = html_de_section(contexte(resultat_de_base()))
        ligne = re.search(r'<tr><th>Fuseau horaire</th>.*?</tr>',
                          html).group(0)
        self.assertIn('Africa/Casablanca', ligne)
        self.assertIn('base IANA', ligne)

    def test_fuseau_absent_dit_source_non_renseignee(self):
        resultat = resultat_de_base()
        resultat['meteo']['heure']['fuseau_site'] = None
        html = html_de_section(contexte(resultat))
        ligne = re.search(r'<tr><th>Fuseau horaire</th>.*?</tr>',
                          html).group(0)
        self.assertIn('source non renseignée', ligne)


class SiteGeographiqueTest(unittest.TestCase):
    def test_ville_adresse_et_repere_viennent_du_contexte_site(self):
        site = {'ville': 'Bouskoura', 'adresse': 'Zone industrielle',
                'pin': {'lat': 33.5, 'lng': -7.6},
                'source': 'lead_roof_point'}
        html = html_de_section(contexte(resultat_de_base(), site=site))
        self.assertIn('Bouskoura', html)
        self.assertIn('Zone industrielle', html)
        self.assertIn('33,5', html)
        self.assertIn('épingle posée par le client', html)

    def test_site_vide_imprime_des_tirets_jamais_une_valeur_inventee(self):
        html = html_de_section(contexte(resultat_de_base(), site={}))
        self.assertIn('<tr><th>Ville</th><td>—</td></tr>', html)
        self.assertIn('<tr><th>Adresse</th><td>—</td></tr>', html)
        self.assertIn('source non renseignée', html)


class PerteDeclareeTest(unittest.TestCase):
    def test_perte_et_commentaire_sont_imprimes(self):
        html = html_de_section(contexte(resultat_de_base()))
        self.assertIn('20,1', html)
        self.assertIn('CAL238', html)


class DansLeRapportTest(unittest.TestCase):
    def test_la_section_passe_par_ce_redacteur_et_sa_feuille_est_en_tete(
            self):
        rapport = construire_rapport(
            SimpleNamespace(company=None, client_id=None, lead_id=None,
                            titre='Villa', resultat=None, pk=None),
            resultat=resultat_de_base(),
            site={}, identite={}, styles={})
        html = html_de_rapport(rapport)
        section = re.search(r'<section class="section-rapport" '
                            r'data-section="site_meteo">.*?</section>',
                            html, re.S).group(0)
        self.assertIn('site-meteo', section)
        self.assertIn('.site-meteo .detail', html.split('</head>')[0])
        self.assertNotIn('<style>', html.split('</head>')[1])


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
