"""CIQ209 — ``economie_ci`` (6/6) : vue INTERNE face à une offre CSE/PPA
concurrente (tarif ÉCRIT du prospect, D-CIQ-16) et ``economie_ci_publique``
qui retire tout l'interne.

SimpleTestCase : aucune base.
"""
import json
import os

from django.test import SimpleTestCase

from apps.ventes import economie as eco_mod
from apps.ventes import economie_ci as eco


def _flux(economie=120000.0, investissement=900000.0, deg=0.0):
    return eco_mod.flux_de_tresorerie(
        investissement_mad={'valeur': investissement, 'source': 'test'},
        economie_annee1_mad={'valeur': economie, 'source': 'test'},
        production_annee1_kwh={'valeur': 100000.0, 'source': 'test'},
        horizon_ans={'valeur': 25, 'source': 'test'},
        indexation_pct={'valeur': 0.0, 'source': 'test'},
        degradation_pct={'valeur': deg, 'source': 'test (saisie à 0)'})


def _offre(**surcharges):
    offre = {'tarif_kwh_ht': 0.85, 'duree_ans': 10,
             'source': 'offre écrite du prospect du 01/10/2026'}
    offre.update(surcharges)
    return offre


class ComparaisonCseTest(SimpleTestCase):
    def test_cumul_offre_850000_recalcule(self):
        res = eco.comparaison_cse(_flux(), _offre(), 100000.0)
        self.assertEqual(res['statut'], 'calculee')
        attendu = sum(0.85 * 100000.0 for _ in range(10))
        self.assertAlmostEqual(attendu, 850000.0, places=6)
        self.assertEqual(res['cumul_offre_mad'], 850000.0)
        self.assertEqual(len(res['annees']), 10)
        self.assertEqual(res['annees'][0]['kwh_livres'], 100000)
        self.assertEqual(res['annees'][0]['paiement_offre_mad'], 85000.0)

    def test_indexation_absente_tarif_constant_hypothese_nommee(self):
        res = eco.comparaison_cse(_flux(), _offre(), 100000.0)
        paiements = {a['paiement_offre_mad'] for a in res['annees']}
        self.assertEqual(paiements, {85000.0})
        hyp = {h['cle']: h for h in res['hypotheses']}
        self.assertEqual(hyp['indexation_pct_an']['statut'], 'hypothese')
        self.assertEqual(hyp['indexation_pct_an']['source'],
                         eco.MENTION_CSE_INDEXATION_ABSENTE)

    def test_indexation_ecrite_appliquee(self):
        res = eco.comparaison_cse(_flux(), _offre(indexation_pct_an=2.0),
                                  100000.0)
        self.assertEqual(res['annees'][1]['paiement_offre_mad'],
                         round(0.85 * 1.02 * 100000.0, 2))

    def test_meme_degradation_que_le_flux(self):
        res = eco.comparaison_cse(_flux(deg=0.5), _offre(), 100000.0)
        self.assertEqual(res['annees'][1]['kwh_livres'],
                         int(round(100000.0 * 0.995)))

    def test_annee_croisement(self):
        # Achat : −900 000 puis +120 000/an ; offre : 120 000 − 85 000 =
        # 35 000/an net. Cumul achat ≥ cumul net offre dès que
        # −900 000 + 120 000 t ≥ 35 000 t ⇔ t ≥ 10,59 ⇒ jamais dans 10 ans.
        res = eco.comparaison_cse(_flux(), _offre(), 100000.0)
        self.assertIsNone(res['annee_croisement'])
        # Investissement 300 000 : −300 000 + 120 000 t ≥ 35 000 t ⇔ t ≥ 3,53.
        res = eco.comparaison_cse(_flux(investissement=300000.0), _offre(),
                                  100000.0)
        self.assertEqual(res['annee_croisement'], 4)

    def test_sans_offre_none(self):
        self.assertIsNone(eco.comparaison_cse(_flux(), None, 100000.0))

    def test_offre_sans_source_refusee(self):
        with self.assertRaises(eco.SaisieEconomieCiInvalide) as ctx:
            eco.comparaison_cse(_flux(), _offre(source=''), 100000.0)
        self.assertEqual(ctx.exception.champ, 'offre_cse_concurrente.source')

    def test_aucun_nom_de_concurrent_recopie(self):
        res = eco.comparaison_cse(
            _flux(), _offre(concurrent='Concurrent SA'), 100000.0)
        self.assertNotIn('Concurrent SA', json.dumps(res, ensure_ascii=False))

    def test_sans_flux_omise(self):
        res = eco.comparaison_cse({'flux': []}, _offre(), 100000.0)
        self.assertEqual(res['statut'], 'omise')
        self.assertEqual(res['motif'], eco.MOTIF_CSE_SANS_FLUX_HT)


class EconomiePubliqueTest(SimpleTestCase):
    def _exemple(self):
        chemin = os.path.join(os.path.dirname(__file__), os.pardir,
                              'contract_samples', 'economie_ci.json')
        with open(chemin, encoding='utf-8') as fh:
            return json.load(fh)['exemple']

    def test_garde_de_cles_recursive(self):
        bloc = self._exemple()
        bloc['vue_interne']['comparaison_cse'] = eco.comparaison_cse(
            _flux(), _offre(), 100000.0)
        bloc['sous_bloc'] = {'alertes_internes': [1],
                             'liste': [{'vue_interne': {}}]}
        public = eco.economie_ci_publique(bloc)

        def cles(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    yield k
                    yield from cles(v)
            elif isinstance(o, list):
                for v in o:
                    yield from cles(v)
        toutes = set(cles(public))
        for interdite in ('vue_interne', 'comparaison_cse',
                          'alertes_internes'):
            self.assertNotIn(interdite, toutes)
        # La copie ne modifie pas le bloc interne.
        self.assertIn('vue_interne', bloc)
        self.assertEqual(public['tarif'], bloc['tarif'])

    def test_aucune_cle_interdite_dans_la_comparaison(self):
        from apps.calepinage.services.note_calcul import (
            CLES_INTERDITES, CLES_INTERDITES_EXACTES)
        res = eco.comparaison_cse(_flux(), _offre(), 100000.0)
        cles = set(res) | set(res['annees'][0])
        for k in cles:
            self.assertNotIn(k, CLES_INTERDITES_EXACTES)
            for interdit in CLES_INTERDITES:
                self.assertNotIn('_%s_' % interdit, '_%s_' % k)
