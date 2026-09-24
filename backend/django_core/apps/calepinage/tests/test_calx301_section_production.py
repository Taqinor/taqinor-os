"""CALX301 — la section « Production » du rapport : mensuel, PR, P50/P90.

Ce qui est prouvé ici, sur le résultat du CONTRAT
(``contract_samples/calepinage_resultat.json``, CALX70) :

* 12 lignes mensuelles pour les 12 entrées de ``production.mensuel[]`` ;
* un ``p90_kwh: null`` imprime « — » et non « 0 » ;
* la mention « quantiles annuels uniquement » (``MENTION_QUANTILES_
  ANNUELS``) est présente dès qu'un P90 est imprimé — qu'il ait une valeur
  ou qu'il soit absent, puisque la ligne P90 fait TOUJOURS partie du même
  bloc que cette mention ;
* la variabilité interannuelle (``annual_variability``) est imprimée avec sa
  NATURE (mesurée sur N années, ou hypothèse — le ``source`` de la
  composante ``variabilite_interannuelle`` du contrat d'incertitude) ; sans
  composante, « source non renseignée », jamais une nature devinée ;
* la table par pan imprime ``production.par_pan[]`` (pan, modules, kWc, P50,
  PR, productible spécifique) ;
* dans le rapport assemblé, la section passe par ce rédacteur et sa feuille
  est posée dans le ``<head>``.

Run :
    cd backend/django_core
    python -m pytest apps/calepinage/tests/test_calx301_section_production.py \
        -q
"""
import copy
import json
import pathlib
import re
import unittest
from html import escape
from types import SimpleNamespace

from apps.calepinage.services.rapport import (
    construire_rapport, html_de_rapport, nombre_tel_que_servi,
)
from apps.calepinage.services.rapport.production import (
    MENTION_QUANTILES_ANNUELS, html_de_section,
)

RACINE_APP = pathlib.Path(__file__).resolve().parents[1]


def _charger(nom):
    return json.loads((RACINE_APP / 'contract_samples' / nom)
                      .read_text(encoding='utf-8'))


RESULTAT = _charger('calepinage_resultat.json')['exemple']
MOTIF = ("Production non simulée : le productible annuel et mensuel n'est "
         "publié qu'après la simulation (onglet Production).")


def contexte(resultat, langue='fr'):
    return {'resultat': resultat, 'langue': langue,
            'section': {'code': 'production', 'motif_si_absent': MOTIF}}


def resultat_de_base():
    return copy.deepcopy(RESULTAT)


class TableMensuelleTest(unittest.TestCase):
    def test_douze_entrees_donnent_douze_lignes(self):
        resultat = resultat_de_base()
        self.assertEqual(len(resultat['production']['mensuel']), 12)
        html = html_de_section(contexte(resultat))
        table = re.search(r'<table class="production-mensuelle[^>]*>(.*?)'
                          r'</table>', html, re.S).group(1)
        self.assertEqual(table.count('<tr>'), 13)  # en-tête + 12 mois

    def test_les_mois_sont_imprimes_en_francais(self):
        html = html_de_section(contexte(resultat_de_base()))
        self.assertIn('Janvier', html)
        self.assertIn('Décembre', html)


class QuantilesTest(unittest.TestCase):
    def test_un_p90_null_imprime_un_tiret_jamais_zero(self):
        resultat = resultat_de_base()
        resultat['production']['total']['p90_kwh'] = None
        html = html_de_section(contexte(resultat))
        ligne = re.search(r'<tr><th>P90 \(kWh\)</th>.*?</tr>',
                          html).group(0)
        self.assertIn('—', ligne)
        self.assertNotIn('<td>0</td>', ligne)
        # La mention annuelle-uniquement reste présente même sans valeur.
        self.assertIn(escape(MENTION_QUANTILES_ANNUELS), html)

    def test_un_p90_present_porte_aussi_la_mention_annuelle(self):
        resultat = resultat_de_base()
        resultat['production']['total']['p90_kwh'] = 11900.0
        html = html_de_section(contexte(resultat))
        ligne = re.search(r'<tr><th>P90 \(kWh\)</th>.*?</tr>',
                          html).group(0)
        self.assertIn(nombre_tel_que_servi(11900.0), ligne)
        self.assertIn(escape(MENTION_QUANTILES_ANNUELS), html)

    def test_la_variabilite_porte_sa_nature_mesuree_sur_n_annees(self):
        html = html_de_section(contexte(resultat_de_base()))
        ligne = re.search(
            r'<tr><th>Variabilité interannuelle</th>.*?</tr>', html).group(0)
        self.assertIn('mesurée sur la série météo', ligne)
        self.assertIn('2 années', ligne)

    def test_sans_composante_la_nature_dit_source_non_renseignee(self):
        resultat = resultat_de_base()
        resultat['incertitude']['composantes'] = []
        html = html_de_section(contexte(resultat))
        ligne = re.search(
            r'<tr><th>Variabilité interannuelle</th>.*?</tr>', html).group(0)
        self.assertIn('source non renseignée', ligne)


class TableParPanTest(unittest.TestCase):
    def test_une_ligne_par_pan(self):
        html = html_de_section(contexte(resultat_de_base()))
        table = re.search(r'<table class="production-par-pan[^>]*>(.*?)'
                          r'</table>', html, re.S).group(1)
        self.assertEqual(table.count('<tr>'), 3)  # en-tête + 2 pans
        self.assertIn('PAN-A', html)
        self.assertIn('PAN-B', html)

    def test_sans_par_pan_aucune_table_par_pan(self):
        resultat = resultat_de_base()
        resultat['production']['par_pan'] = []
        html = html_de_section(contexte(resultat))
        self.assertNotIn('production-par-pan', html)


class TotauxTest(unittest.TestCase):
    def test_pr_et_productible_specifique_sont_imprimes(self):
        html = html_de_section(contexte(resultat_de_base()))
        self.assertIn('0,799', html)
        self.assertIn('1504,6', html)


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
                            r'data-section="production">.*?</section>',
                            html, re.S).group(0)
        self.assertIn('production-mensuelle', section)
        self.assertIn('.production-quantiles .detail',
                      html.split('</head>')[0])
        self.assertNotIn('<style>', html.split('</head>')[1])


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
