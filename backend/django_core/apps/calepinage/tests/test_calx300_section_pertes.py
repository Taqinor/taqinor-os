"""CALX300 — la section « Chaîne de pertes » du rapport, séquentielle, en table.

Ce qui est prouvé ici, sur la cascade du CONTRAT
(``contract_samples/calepinage_pertes_cascade.json``, CALX141) :

* la DERNIÈRE valeur ``kwh_apres`` imprimée est exactement celle du contrat —
  aucune arithmétique locale : ni arrondi (``15792.34`` s'imprime
  ``15792,34``), ni total recalculé (un ``total_pct`` servi incohérent est
  imprimé TEL QUEL) ;
* six colonnes, de l'irradiance incidente à l'énergie livrée, plus la ligne de
  total ;
* un poste NON SOURCÉ est imprimé hachuré ET nommé (« source non
  renseignée »), jamais masqué ; une étape omise s'imprime « omis » avec son
  motif, jamais « 0 » ; un gain garde son signe servi ;
* sans cascade, la section imprime la liste plate EN DISANT que la cascade
  n'a pas été produite — jamais une table vide ; sans l'une ni l'autre, la
  phrase de motif ;
* dans le rapport assemblé, la section passe par ce rédacteur et sa feuille
  est posée dans le ``<head>``.

Run :
    cd backend/django_core
    python -m pytest apps/calepinage/tests/test_calx300_section_pertes.py -q
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
from apps.calepinage.services.rapport.pertes import (
    MENTION_CASCADE_ABSENTE, energie_livree, html_de_section,
)

RACINE_APP = pathlib.Path(__file__).resolve().parents[1]


def _charger(nom):
    return json.loads((RACINE_APP / 'contract_samples' / nom)
                      .read_text(encoding='utf-8'))


CASCADE = _charger('calepinage_pertes_cascade.json')
RESULTAT = _charger('calepinage_resultat.json')
MOTIF = ("Ni cascade de pertes ni poste de perte déclaré : lancez la "
         "simulation (onglet Production), ou déclarez les postes dans "
         "l'éditeur de pertes.")


def contexte(resultat, langue='fr'):
    return {'resultat': resultat, 'langue': langue,
            'section': {'code': 'pertes', 'motif_si_absent': MOTIF}}


def cascade_du_contrat():
    return copy.deepcopy(CASCADE['exemple']['cascade'])


def cellules(html, classe):
    """Le texte des cellules ``classe`` (sans leur ligne de détail)."""
    brutes = re.findall(r'<td class="kwh %s">(.*?)</td>' % classe, html)
    return [re.sub(r'<span class="detail">.*?</span>', '', c).strip()
            for c in brutes]


class AucuneArithmetiqueTest(unittest.TestCase):
    def test_la_derniere_energie_imprimee_est_celle_du_contrat(self):
        cascade = cascade_du_contrat()
        html = html_de_section(contexte({'cascade': cascade}))
        imprimees = [c for c in cellules(html, 'kwh-apres') if c != '—']
        attendue = [e['kwh_apres'] for e in cascade['etapes']
                    if e['kwh_apres'] is not None][-1]
        self.assertEqual(imprimees[-1], nombre_tel_que_servi(attendue))
        self.assertEqual(imprimees[-1], '15792,3')
        self.assertEqual(energie_livree(cascade), attendue)

    def test_aucun_arrondi(self):
        cascade = cascade_du_contrat()
        cascade['etapes'][4]['kwh_apres'] = 15792.34
        html = html_de_section(contexte({'cascade': cascade}))
        self.assertEqual([c for c in cellules(html, 'kwh-apres')
                          if c != '—'][-1], '15792,34')

    def test_le_total_imprime_est_celui_servi_jamais_recalcule(self):
        cascade = cascade_du_contrat()
        cascade['total_pct'] = 99.9      # volontairement incohérent
        html = html_de_section(contexte({'cascade': cascade}))
        total = re.search(r'<tr class="total">.*?</tr>', html).group(0)
        self.assertIn('<td>99,9</td>', total)

    def test_l_irradiance_incidente_est_le_premier_kwh_avant(self):
        html = html_de_section(contexte({'cascade': cascade_du_contrat()}))
        total = re.search(r'<tr class="total">.*?</tr>', html).group(0)
        self.assertIn('16800,0', total)
        self.assertIn('Irradiance incidente', total)
        self.assertIn('Énergie livrée', total)


class TableTest(unittest.TestCase):
    def setUp(self):
        self.html = html_de_section(contexte({'cascade': cascade_du_contrat()}))

    def test_six_colonnes_et_une_ligne_par_etape_plus_le_total(self):
        entete = re.search(r'<table class="pertes-cascade"><tr>(.*?)</tr>',
                           self.html).group(1)
        self.assertEqual(entete.count('<th'), 6)
        self.assertEqual(len(re.findall(r'<tr[^>]*data-etape=', self.html)),
                         len(cascade_du_contrat()['etapes']))
        self.assertEqual(self.html.count('<tr class="total">'), 1)

    def test_un_poste_non_source_est_hachure_et_nomme(self):
        ligne = re.search(r'<tr class="[^"]*non-source[^"]*" '
                          r'data-etape="indisponibilite">.*?</tr>',
                          self.html)
        self.assertIsNotNone(ligne, 'poste non sourcé masqué ou non hachuré')
        self.assertIn('source non renseignée', ligne.group(0))
        self.assertIn('Indisponibilité réseau et maintenance', ligne.group(0))

    def test_une_etape_omise_dit_omis_et_son_motif_jamais_zero(self):
        ligne = re.search(r'<tr[^>]*data-etape="spectral">.*?</tr>',
                          self.html).group(0)
        self.assertIn('<td>omis</td>', ligne)
        self.assertIn('D-CALX 16', ligne)
        self.assertNotIn('<td>0</td>', ligne)

    def test_un_gain_garde_son_signe_servi(self):
        ligne = re.search(r'<tr[^>]*data-etape="bifacial">.*?</tr>',
                          self.html).group(0)
        self.assertIn('-3,0 (gain)', ligne)

    def test_la_source_et_sa_reference_sont_imprimees(self):
        ligne = re.search(r'<tr[^>]*data-etape="irradiation_plan">.*?</tr>',
                          self.html).group(0)
        self.assertIn('PVGIS', ligne)
        self.assertIn('PVGIS-SARAH3', ligne)

    def test_les_postes_non_sources_sont_rappeles(self):
        self.assertIn('availability', self.html)

    def test_les_en_tetes_suivent_la_langue(self):
        html = html_de_section(contexte({'cascade': cascade_du_contrat()},
                                        langue='en'))
        self.assertIn('Energy out (kWh)', html)
        self.assertIn('Chain total', html)


class SansCascadeTest(unittest.TestCase):
    def test_la_liste_plate_est_imprimee_en_le_disant(self):
        pertes = copy.deepcopy(RESULTAT['exemple']['pertes'])
        for cascade in (None, CASCADE['exemple_vide']['cascade']):
            with self.subTest(cascade=cascade):
                html = html_de_section(contexte({'cascade': cascade,
                                                 'pertes': pertes}))
                self.assertIn(escape(MENTION_CASCADE_ABSENTE), html)
                self.assertEqual(len(re.findall(r'<tr(?: class="non-source")?>'
                                                r'<td>', html)), len(pertes))
                self.assertNotIn('<tr class="total">', html)
        # Le poste sans source de la liste plate reste nommé, hachuré.
        self.assertIn('<tr class="non-source"><td>Indisponibilité', html)

    def test_ni_cascade_ni_liste_rend_le_motif_pas_une_table_vide(self):
        html = html_de_section(contexte({'cascade': None, 'pertes': []}))
        self.assertNotIn('<table', html)
        self.assertIn(escape(MOTIF), html)


class DansLeRapportTest(unittest.TestCase):
    def test_la_section_passe_par_ce_redacteur_et_sa_feuille_est_en_tete(self):
        rapport = construire_rapport(
            SimpleNamespace(company=None, client_id=None, lead_id=None,
                            titre='Villa', resultat=None, pk=1),
            resultat=copy.deepcopy(RESULTAT['exemple']),
            site={}, identite={}, styles={})
        html = html_de_rapport(rapport)
        section = re.search(r'<section class="section-rapport" '
                            r'data-section="pertes">.*?</section>',
                            html, re.S).group(0)
        self.assertIn('pertes-cascade', section)
        self.assertIn('repeating-linear-gradient', html.split('</head>')[0])
        self.assertNotIn('<style>', html.split('</head>')[1])


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
