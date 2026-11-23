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
         "publié qu'après la simulation (étape Résultats).")


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


class ColonneIrradiationTest(unittest.TestCase):
    """ACAL452 — l'irradiation dans le plan, telle que servie."""

    def _table(self, resultat):
        html = html_de_section(contexte(resultat))
        return html, re.search(r'<table class="production-mensuelle[^>]*>'
                               r'(.*?)</table>', html, re.S).group(1)

    def test_colonne_presente_avec_les_valeurs_servies(self):
        resultat = resultat_de_base()
        html, table = self._table(resultat)
        self.assertIn('Irradiation dans le plan (kWh/m²)', table)
        for e in resultat['production']['irradiation_mensuelle']:
            self.assertIn('<td class="valeur">%s</td>' % nombre_tel_que_servi(
                e['irradiation_plan_kwh_m2']), table)
        self.assertNotIn('non publiée par cette simulation', html)

    def test_un_mois_null_imprime_un_tiret_jamais_zero(self):
        resultat = resultat_de_base()
        resultat['production']['irradiation_mensuelle'][0][
            'irradiation_plan_kwh_m2'] = None
        _, table = self._table(resultat)
        premiere = table.split('</tr>')[1]
        self.assertIn('Janvier', premiere)
        self.assertIn('<td class="valeur">—</td>', premiere)
        self.assertNotIn('>0<', premiere)

    def test_sans_la_cle_colonne_omise_et_note_imprimee(self):
        resultat = resultat_de_base()
        del resultat['production']['irradiation_mensuelle']
        html, table = self._table(resultat)
        self.assertNotIn('Irradiation dans le plan', table)
        self.assertIn('Irradiation mensuelle non publiée par cette '
                      'simulation : relancez-la', html)


class ColonnesBilanMensuelTest(unittest.TestCase):
    """ACAL708 — irradiation horizontale, température ambiante et PR, telles
    que servies ; ``null`` -> « — » ; bloc absent -> colonne absente."""

    def _table(self, resultat):
        html = html_de_section(contexte(resultat))
        return re.search(r'<table class="production-mensuelle[^>]*>'
                         r'(.*?)</table>', html, re.S).group(1)

    def test_trois_colonnes_avec_les_valeurs_servies(self):
        resultat = resultat_de_base()
        table = self._table(resultat)
        for titre in ('Irradiation horizontale (kWh/m²)',
                      'Température ambiante (°C)', 'PR'):
            self.assertIn('<th>%s</th>' % titre, table)
        premiere = table.split('</tr>')[1]
        production = resultat['production']
        self.assertIn('<td class="valeur">%s</td>' % nombre_tel_que_servi(
            production['gain_inclinaison']['ghi_mensuel'][0]['ghi_kwh_m2']),
            premiere)
        self.assertIn('<td class="valeur">%s</td>' % nombre_tel_que_servi(
            production['bilan_mensuel'][0]['pr']), premiere)
        # la température du contrat est null : « — », jamais 0
        self.assertIn('<td class="valeur">—</td>', premiere)
        self.assertNotIn('>0<', premiere)

    def test_une_valeur_null_imprime_un_tiret(self):
        resultat = resultat_de_base()
        resultat['production']['bilan_mensuel'][0]['pr'] = None
        premiere = self._table(resultat).split('</tr>')[1]
        self.assertEqual(premiere.count('—'), 2)  # température + PR

    def test_bloc_absent_colonne_absente(self):
        resultat = resultat_de_base()
        del resultat['production']['bilan_mensuel']
        resultat['production']['gain_inclinaison'] = None
        table = self._table(resultat)
        self.assertNotIn('Irradiation horizontale', table)
        self.assertNotIn('Température ambiante', table)
        self.assertNotIn('<th>PR</th>', table)
        self.assertIn('Irradiation dans le plan', table)


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


class MiseEnFormeR318Test(unittest.TestCase):
    """R3-18 — milliers groupés à la française, variabilité en pourcentage :
    deux mises en forme, aucun chiffre changé."""

    def test_les_milliers_se_groupent_sans_arrondir(self):
        self.assertEqual(nombre_tel_que_servi(526951.428),
                         '526 951,428')
        self.assertEqual(nombre_tel_que_servi(526951.428, 'en'),
                         '526,951.428')
        self.assertEqual(nombre_tel_que_servi(999.5), '999,5')
        self.assertEqual(nombre_tel_que_servi(2024), '2024')

    def test_la_variabilite_s_imprime_en_pourcentage_exact(self):
        resultat = resultat_de_base()
        resultat['production']['total']['annual_variability'] = 0.0753
        html = html_de_section(contexte(resultat))
        ligne = re.search(
            r'<tr><th>Variabilité interannuelle</th>.*?</tr>', html).group(0)
        self.assertIn('7,53 %', ligne)
        self.assertNotIn('0,0753', ligne)


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
        self.assertIn('1 504,6', html)  # R3-18 : milliers groupés


class TablePluriannuelleTest(unittest.TestCase):
    """ACAL694 — « Production année par année » : valeurs TELLES QUE SERVIES,
    garantie sur les lignes d'année 10 et 25, motif quand omise."""

    def _table(self, resultat):
        html = html_de_section(contexte(resultat))
        trouve = re.search(r'<table class="production-pluriannuelle[^>]*>'
                           r'(.*?)</table>', html, re.S)
        return html, (trouve.group(1) if trouve else None)

    def _resultat(self):
        resultat = resultat_de_base()
        production = resultat['production']
        production['projection'] = [
            {'annee': a, 'facteur': 1.0 - 0.005 * a,
             'p50_kwh': 13000.0 - 70.0 * a, 'source': 'lineaire'}
            for a in (1, 2, 10, 25)]
        return resultat

    def test_lignes_imprimees_telles_que_servies(self):
        resultat = self._resultat()
        html, table = self._table(resultat)
        self.assertIn('Production année par année', html)
        for ligne in resultat['production']['projection']:
            self.assertIn('<td class="valeur">%s</td>' % nombre_tel_que_servi(
                ligne['p50_kwh']), table)
            self.assertIn('<td class="valeur">%s</td>' % nombre_tel_que_servi(
                ligne['facteur']), table)
        self.assertEqual(table.count('<tr>'), 5)  # en-tête + 4 années
        self.assertIn("L'année est un rang, pas un millésime", html)

    def test_garantie_servie_sur_les_lignes_10_et_25_seulement(self):
        resultat = self._resultat()
        garantie = resultat['production']['duree_de_vie']['garantie']
        _, table = self._table(resultat)
        lignes = table.split('</tr>')
        par_annee = {int(re.search(r'<td>(\d+)</td>', ligne).group(1)): ligne
                     for ligne in lignes if re.search(r'<td>\d+</td>', ligne)}
        self.assertIn('>%s</td>' % nombre_tel_que_servi(
            garantie['pct_a_10_ans']), par_annee[10])
        self.assertIn('>%s</td>' % nombre_tel_que_servi(
            garantie['pct_a_25_ans']), par_annee[25])
        for annee in (1, 2):
            self.assertTrue(par_annee[annee].rstrip().endswith('—</td>'))

    def test_motif_d_omission_remplace_la_table(self):
        resultat = self._resultat()
        resultat['production']['duree_de_vie']['motif_omission'] = (
            'Dégradation absente de la fiche du panneau.')
        html, table = self._table(resultat)
        self.assertIsNone(table)
        self.assertIn('Dégradation absente de la fiche du panneau.', html)

    def test_sans_projection_ni_motif_rien_n_est_imprime(self):
        resultat = resultat_de_base()
        resultat['production']['projection'] = None
        resultat['production']['duree_de_vie'] = None
        html, table = self._table(resultat)
        self.assertIsNone(table)
        self.assertNotIn('Production année par année', html)


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
