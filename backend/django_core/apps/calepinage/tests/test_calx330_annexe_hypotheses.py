"""CALX330 — l'annexe « hypothèses, sources et omissions » du rapport.

Ce qui est prouvé ici :

* une perte ``source: null`` apparaît dans la table des hypothèses avec
  « source non renseignée » (le MÊME texte que ``note_calcul``) ; une
  source connue est traduite (glossaire partagé) ;
* la cascade prime sur la liste plate quand les deux existent (même
  préférence que la section ``pertes``, CALX300) ; une étape OMISE de la
  cascade n'entre PAS dans les hypothèses employées ;
* une grandeur OMISE (``entrees_exigees`` manquant à une section du
  contrat) apparaît dans la table « non calculé » avec le motif de la
  section propriétaire — le même texte qu'elle imprime déjà à sa place ;
* les deux tables sont DISJOINTES : aucune grandeur des deux à la fois ;
* aucun mot de montant dans le rendu ;
* dans le rapport assemblé, la section passe par ce rédacteur et sa
  feuille est posée dans le ``<head>``.

Run :
    cd backend/django_core
    python -m pytest apps/calepinage/tests/test_calx330_annexe_hypotheses.py -q
"""
import copy
import json
import pathlib
import re
import unittest
from html import escape
from types import SimpleNamespace

from apps.calepinage.services.rapport import (
    construire_rapport, html_de_rapport, sections_declarees,
)
from apps.calepinage.services.rapport.annexe_hypotheses import (
    SOURCE_NON_RENSEIGNEE, html_de_section,
)

RACINE_APP = pathlib.Path(__file__).resolve().parents[1]

#: Mêmes jetons que ``test_calx297_rapport_etude.py`` (D5 — aucun montant
#: dans une pièce technique).
MOTS_DE_MONTANT = re.compile(
    r'(?<![\w-])(MAD|DH|prix|coût|cout|montant|remise|TTC|HT)(?![\w-])|€',
    re.IGNORECASE)


def _charger(nom):
    return json.loads((RACINE_APP / 'contract_samples' / f'{nom}.json')
                      .read_text(encoding='utf-8'))


RESULTAT = _charger('calepinage_resultat')
#: La cascade du contrat CALX141 — toute étape de test en est extraite,
#: JAMAIS un littéral de perte en dur (garde CAL238,
#: ``test_politique_pertes_pvgis.AucunePerteCacheeTest``).
CASCADE = _charger('calepinage_pertes_cascade')


def _etape_du_contrat(indice=0):
    """Une étape RÉELLE de la cascade du contrat, jamais un littéral en dur."""
    return copy.deepcopy(CASCADE['exemple']['cascade']['etapes'][indice])


def contexte(resultat, langue='fr'):
    motif = "L'annexe s'imprime toujours."
    section = {'code': 'hypotheses', 'motif_si_absent': motif}
    return {'resultat': resultat, 'langue': langue, 'section': section}


def table_employees(html):
    """Le fragment HTML entre les deux titres — la table des hypothèses."""
    return html.split('Non calculé')[0]


def table_non_calcule(html):
    return html.split('Non calculé')[1]


class SourceNonRenseigneeTest(unittest.TestCase):
    def test_une_perte_sans_source_affiche_source_non_renseignee(self):
        resultat = {'cascade': None, 'pertes': [
            {'poste': 'availability',
             'libelle': 'Indisponibilité réseau et maintenance',
             'pct': 1.0, 'source': None}]}
        html = html_de_section(contexte(resultat))
        self.assertIn(SOURCE_NON_RENSEIGNEE, html)
        self.assertIn('Indisponibilité réseau et maintenance', html)
        self.assertIn('class="non-source"', html)

    def test_une_source_connue_est_traduite(self):
        resultat = {'cascade': None, 'pertes': [
            {'poste': 'shading', 'libelle': 'Ombrage proche', 'pct': 3.4,
             'source': 'mesure'}]}
        html = html_de_section(contexte(resultat))
        self.assertIn('mesure', html)
        self.assertNotIn(SOURCE_NON_RENSEIGNEE, html)


class PreferenceCascadeTest(unittest.TestCase):
    def test_la_cascade_prime_sur_la_liste_plate(self):
        etape = _etape_du_contrat()
        resultat = {
            'cascade': {'etapes': [etape]},
            'pertes': [{'poste': 'wiring', 'libelle': 'Pertes ohmiques',
                       'pct': 2.0, 'source': 'hypothese'}],
        }
        html = html_de_section(contexte(resultat))
        self.assertIn(etape['libelle'], table_employees(html))
        self.assertNotIn('Pertes ohmiques', html)

    def test_une_etape_omise_n_entre_pas_dans_les_hypotheses_employees(self):
        resultat = {'cascade': {'etapes': [
            {'etape': 'spectral', 'libelle': 'Correction spectrale',
             'perte_pct': None, 'source': None,
             'motif_omission': 'D-CALX 16 — toujours omis, jamais '
                               'forfaitisé.'}]}}
        html = html_de_section(contexte(resultat))
        self.assertNotIn('Correction spectrale', table_employees(html))

    def test_sans_cascade_ni_pertes_la_table_est_vide_mais_presente(self):
        html = html_de_section(contexte({}))
        self.assertIn('Hypothèses employées', html)
        self.assertEqual(table_employees(html).count('<tr'), 1)  # en-tête


class ReferenceEtDateTest(unittest.TestCase):
    def test_la_reference_est_imprimee_quand_elle_existe(self):
        etape = _etape_du_contrat()
        resultat = {'cascade': {'etapes': [etape]}}
        html = html_de_section(contexte(resultat))
        self.assertIn(etape['reference'], html)

    def test_sans_date_de_saisie_le_tiret_s_imprime(self):
        html = html_de_section(contexte({'cascade': None, 'pertes': [
            {'poste': 'wiring', 'libelle': 'Pertes ohmiques', 'pct': 2.0,
             'source': 'hypothese'}]}))
        self.assertIn('<td>—</td>', table_employees(html))

    def test_une_date_de_saisie_publiee_est_imprimee(self):
        html = html_de_section(contexte({'cascade': None, 'pertes': [
            {'poste': 'wiring', 'libelle': 'Pertes ohmiques', 'pct': 2.0,
             'source': 'saisie', 'date_saisie': '2026-09-01'}]}))
        self.assertIn('2026-09-01', html)


class ValeurTelleQueServieTest(unittest.TestCase):
    def test_aucun_arrondi(self):
        html = html_de_section(contexte({'cascade': None, 'pertes': [
            {'poste': 'x', 'libelle': 'X', 'pct': 3.456, 'source': 'mesure'}
        ]}))
        self.assertIn('3,456', html)


class NonCalculeTest(unittest.TestCase):
    def setUp(self):
        self.html = html_de_section(contexte(
            copy.deepcopy(RESULTAT['exemple_vide'])))
        self.non_calcule = table_non_calcule(self.html)

    def test_une_grandeur_omise_apparait_avec_le_motif_du_service(self):
        declarees = {s['code']: s for s in sections_declarees()}
        motif_production = declarees['production']['motif_si_absent']
        self.assertIn('production.total.p50_kwh', self.non_calcule)
        self.assertIn(escape(motif_production), self.non_calcule)

    def test_toutes_les_grandeurs_manquantes_sont_listees(self):
        for chemin in ('production.total.p50_kwh', 'production.mensuel[]',
                       'ombrage.par_pan[]', 'electrique.chainage',
                       'electrique.verdicts[]', 'electrique.onduleurs[]'):
            with self.subTest(chemin=chemin):
                self.assertIn(escape(chemin), self.non_calcule)

    def test_un_resultat_complet_ne_publie_aucune_omission(self):
        html = html_de_section(contexte(copy.deepcopy(RESULTAT['exemple'])))
        non_calcule = table_non_calcule(html)
        self.assertEqual(non_calcule.count('<tr'), 1)  # en-tête seule


class TablesDisjointesTest(unittest.TestCase):
    def test_aucune_grandeur_dans_les_deux_tables_a_la_fois(self):
        resultat = copy.deepcopy(RESULTAT['exemple'])
        # On retire une grandeur exigée : elle doit apparaître SEULEMENT
        # dans « non calculé », jamais dans « hypothèses employées ».
        del resultat['production']['total']['p50_kwh']
        html = html_de_section(contexte(resultat))
        employees, non_calcule = (table_employees(html),
                                  table_non_calcule(html))
        self.assertIn('production.total.p50_kwh', non_calcule)
        self.assertNotIn('production.total.p50_kwh', employees)
        # Et un poste RÉELLEMENT employé (la cascade) reste seulement dans
        # la première table.
        self.assertIn('Irradiation sur le plan des modules', employees)
        self.assertNotIn('Irradiation sur le plan des modules', non_calcule)


class AucunMontantTest(unittest.TestCase):
    def test_aucun_mot_de_montant(self):
        for cle in ('exemple', 'exemple_vide'):
            with self.subTest(resultat=cle):
                html = html_de_section(
                    contexte(copy.deepcopy(RESULTAT[cle])))
                texte = re.sub(r'<[^>]+>', ' ', html)
                self.assertIsNone(MOTS_DE_MONTANT.search(texte),
                                  MOTS_DE_MONTANT.search(texte))


class DansLeRapportTest(unittest.TestCase):
    def test_la_section_passe_par_ce_redacteur_et_sa_feuille_est_en_tete(self):
        rapport = construire_rapport(
            SimpleNamespace(company=None, client_id=None, lead_id=None,
                            titre='Villa', resultat=None, pk=None),
            resultat=copy.deepcopy(RESULTAT['exemple']),
            site={}, identite={}, styles={})
        html = html_de_rapport(rapport)
        section = re.search(r'<section class="section-rapport" '
                            r'data-section="hypotheses">.*?</section>',
                            html, re.S).group(0)
        self.assertIn('annexe-hypotheses', section)
        self.assertIn('.annexe-hypotheses td', html.split('</head>')[0])
        self.assertNotIn('<style>', html.split('</head>')[1])


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
