"""AGR306 — textes réglementaires du devis agricole : la RÈGLE de l'aide FDA
(sans montant, D-AGR-6) et les formalités du client (82-21, 36-15), en
fr / en / ar.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_agr306_mentions_agricoles"
"""
import json
from pathlib import Path

from django.test import SimpleTestCase, TestCase

from apps.ventes.quote_engine.agricole import mentions
from apps.ventes.quote_engine.agricole.mentions import (
    LANGUES, PLAFONDS, formalites, phrase_provenance, regle_fda,
)
from apps.ventes.quote_engine.agricole.synthese import synthese_agricole

CONTRAT = json.loads(
    (Path(__file__).resolve().parent.parent / 'contract_samples'
     / 'proposal_data.json').read_text(encoding='utf-8'))[
        'exemple_agricole']['synthese_agricole']

REGLE_SOCIETE = {
    'taux_pct': 25, 'plafond_mad_par_ha': 2500,
    'plafond_mad_par_kwc': 2800, 'plafond_mad_par_projet': 25000,
    'base': 'ttc', 'source': 'Guide FDA édition 2025, p.18-21',
    'releve_le': '2026-11-15',
}


def _feuilles(o):
    if isinstance(o, dict):
        for v in o.values():
            yield from _feuilles(v)
    elif isinstance(o, (list, tuple)):
        for v in o:
            yield from _feuilles(v)
    else:
        yield o


def _cles(o):
    if isinstance(o, dict):
        for k, v in o.items():
            yield k
            yield from _cles(v)
    elif isinstance(o, (list, tuple)):
        for v in o:
            yield from _cles(v)


def _textes(o):
    return [v for v in _feuilles(o) if isinstance(v, str)]


class RegleFdaTests(SimpleTestCase):
    def test_regle_societe_remplace_le_repli(self):
        r = regle_fda(REGLE_SOCIETE)
        self.assertEqual(r['plafonds'], {
            'taux_pct': 25, 'plafond_mad_par_ha': 2500,
            'plafond_mad_par_kwc': 2800, 'plafond_mad_par_projet': 25000})
        self.assertEqual(r['source'], REGLE_SOCIETE['source'])
        self.assertEqual(r['edition'], REGLE_SOCIETE['source'])
        self.assertEqual(r['releve_le'], '2026-11-15')
        self.assertIn('25 000 DH par projet', r['textes']['fr'])
        self.assertIn('25,000 MAD per project', r['textes']['en'])

    def test_regle_vide_repli_date_guide_fda_2024(self):
        for vide in (None, {}, {'taux_pct': 50}):
            with self.subTest(vide=vide):
                r = regle_fda(vide)
                self.assertEqual(r['edition'], 'Guide FDA 2024')
                self.assertIn('2024', r['source'])
                self.assertIn('p.20-23', r['source'])
                self.assertEqual(r['releve_le'], '2026-10-02')
                self.assertEqual(r['plafonds'], {
                    'taux_pct': 30, 'plafond_mad_par_ha': 3000,
                    'plafond_mad_par_kwc': 3000,
                    'plafond_mad_par_projet': 30000})

    def test_forme_du_contrat(self):
        r = regle_fda()
        self.assertEqual(set(r), set(CONTRAT['aide_fda']))
        self.assertEqual(set(r['plafonds']), set(CONTRAT['aide_fda']
                                                 ['plafonds']))
        self.assertEqual(set(r['textes']), set(LANGUES))
        for f in formalites():
            self.assertEqual(set(f), set(CONTRAT['formalites'][0]))

    def test_aucun_nombre_hors_plafonds_ni_montant_client(self):
        for regle in (None, REGLE_SOCIETE):
            r = regle_fda(regle)
            permis = {r['plafonds'][c] for c in PLAFONDS}
            nombres = [v for v in _feuilles(r)
                       if isinstance(v, (int, float))
                       and not isinstance(v, bool)]
            self.assertTrue(set(nombres) <= permis, nombres)
            for cle in ('montant', 'montant_fda', 'montant_aide', 'aide_mad',
                        'fda_eligible', 'delai', 'delai_jours'):
                self.assertNotIn(cle, set(_cles(r)))

    def test_jamais_jusqu_a_ni_cumulable(self):
        tout = (_textes(regle_fda()) + _textes(regle_fda(REGLE_SOCIETE))
                + _textes(formalites())
                + _textes(mentions.PHRASES_PROVENANCE))
        for texte in tout:
            bas = texte.lower()
            self.assertNotIn('jusqu', bas)
            self.assertNotIn('up to', bas)
            self.assertNotIn('cumul', bas)

    def test_conditions_et_accord_prealable(self):
        r = regle_fda()
        self.assertIn('accord préalable obtenu AVANT les travaux',
                      r['conditions'])
        self.assertIn('un seul projet par exploitation', r['conditions'])
        self.assertIn('AVANT les travaux', r['textes']['fr'])
        self.assertIn("n'est pas organisme subventionneur", r['textes']['fr'])


class FormalitesEtPhrasesTests(SimpleTestCase):
    def test_formalites_presentes_trois_langues(self):
        f = {x['cle']: x for x in formalites()}
        self.assertEqual(set(f), {'declaration_8221', 'prelevement_3615'})
        for x in f.values():
            self.assertEqual(set(x['textes']), set(LANGUES))
            self.assertTrue(all(x['textes'][lg].strip() for lg in LANGUES))
        self.assertIn('82-21, art. 3', f['declaration_8221']['textes']['fr'])
        self.assertIn('à la charge du client',
                      f['prelevement_3615']['textes']['fr'])

    def test_36_15_sans_article_tant_que_le_texte_n_est_pas_relu(self):
        self.assertIsNone(mentions.LOI_36_15_URL)
        f = {x['cle']: x for x in formalites()}['prelevement_3615']
        self.assertNotIn('art.', f['textes']['fr'])
        self.assertIn('loi 36-15', f['textes']['fr'])

    def test_aucune_injection_ni_revente(self):
        for texte in _textes(formalites()):
            self.assertNotIn('injection', texte.lower())
            self.assertNotIn('revente', texte.lower())

    def test_phrases_de_provenance(self):
        self.assertEqual(phrase_provenance('declare', date='2026-09-12'),
                         'déclaré par vous le 12/09/2026')
        self.assertEqual(
            phrase_provenance('mesure', date='2026-09-15'),
            "mesuré par l'installateur le 15/09/2026")
        self.assertEqual(
            phrase_provenance('mesure', date='2026-09-15',
                              nom_societe='Solaire Atlas'),
            'mesuré par Solaire Atlas le 15/09/2026')
        self.assertEqual(phrase_provenance('declare'),
                         'à confirmer par la visite')
        self.assertEqual(phrase_provenance('agronomique'),
                         'besoin agronomique plein (FAO-56)')
        for cle, langues in mentions.PHRASES_PROVENANCE.items():
            self.assertEqual(set(langues), set(LANGUES), cle)


class SyntheseTests(SimpleTestCase):
    def test_toute_synthese_porte_la_regle_et_les_formalites(self):
        for data in ({}, {'mode_installation': 'agricole', 'etude': {}}):
            s = synthese_agricole(data)
            self.assertEqual(s['aide_fda']['source'],
                             'Guide FDA édition 2024, p.20-23')
            self.assertEqual(s['aide_fda']['plafonds']['taux_pct'], 30)
            self.assertEqual(len(s['formalites']), 2)

    def test_la_regle_societe_passee_par_le_builder_est_imprimee(self):
        s = synthese_agricole({'regle_fda_societe': REGLE_SOCIETE,
                               'entreprise': {'nom': 'Soleil SARL'}})
        self.assertEqual(s['aide_fda']['plafonds']['plafond_mad_par_ha'],
                         2500)
        self.assertIn('Soleil SARL', s['aide_fda']['textes']['fr'])


class BuilderTests(TestCase):
    def test_builder_passe_la_regle_saisie_pour_l_agricole_seulement(self):
        from apps.parametres.models_tariff import TariffSettings
        from apps.ventes.quote_engine.builder import build_quote_data
        from testkit.factories import CompanyFactory, DevisFactory

        company = CompanyFactory()
        agricole = DevisFactory(company=company, mode_installation='agricole')
        residentiel = DevisFactory(company=company,
                                   mode_installation='residentiel')
        data = build_quote_data(agricole, {'pdf_mode': 'full'})
        self.assertNotIn('regle_fda_societe', data)
        TariffSettings.objects.update_or_create(
            company=company, defaults={'regle_fda_pompage': REGLE_SOCIETE})
        data = build_quote_data(agricole, {'pdf_mode': 'full'})
        self.assertEqual(data['regle_fda_societe']['plafond_mad_par_projet'],
                         25000)
        self.assertEqual(
            synthese_agricole(data)['aide_fda']['releve_le'], '2026-11-15')
        # Résidentiel sans onduleur : le format à options est refusé (règle
        # dure) ; la clé vérifiée ne dépend pas du format.
        data = build_quote_data(residentiel, {'pdf_mode': 'onepage'})
        self.assertNotIn('regle_fda_societe', data)
