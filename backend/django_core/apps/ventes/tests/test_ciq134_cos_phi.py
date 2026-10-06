"""CIQ134 — Industriel MT : alerte INTERNE de facteur de puissance après PV
(jamais un chiffre client), calculée UNE fois par ``moteur_ci.reactif`` et
relayée par ``economie_ci.alertes_internes``.

SimpleTestCase : aucune base.
"""
import ast
import copy
import json
import os

from django.test import SimpleTestCase

from apps.ventes import economie_ci as eco
from apps.ventes.domain import etude_ci
from apps.ventes.moteur_ci import reactif
from apps.ventes.quote_engine.ci.synthese import synthese_ci

_ICI = os.path.dirname(__file__)
_VENTES = os.path.join(_ICI, os.pardir)


def _cas_reference(**surcharges):
    entrees = dict(tension='mt', kwh_mensuels=[100000.0],
                   autoconso_mensuels=[40000.0], kvarh_mensuels=[60000.0])
    entrees.update(surcharges)
    return reactif.evaluer_reactif(**entrees)


class ReactifTest(SimpleTestCase):
    def test_cas_de_reference_alerte_interne_sourcee(self):
        res = _cas_reference()
        self.assertEqual(res['statut'], 'evalue')
        mois = res['par_mois'][0]
        # cos φ avant = 100 000 / √(100 000² + 60 000²) = 0,857 ;
        # après = 60 000 / √(60 000² + 60 000²) = 0,707.
        self.assertEqual(mois['cos_phi_avant'], 0.857)
        self.assertEqual(mois['cos_phi_apres'], 0.707)
        self.assertEqual(len(res['alertes']), 1)
        alerte = res['alertes'][0]
        self.assertEqual(alerte['code'], 'cos_phi_apres_pv')
        self.assertIs(alerte['interne'], True)
        self.assertEqual(set(alerte),
                         {'code', 'champ', 'message', 'niveau', 'interne'})
        for attendu in (reactif.SOURCE_SEUIL, reactif.DATE_SOURCE,
                        reactif.MENTION_A_CONFIRMER,
                        reactif.MENTION_ESTIMATION, reactif.QUESTION_VISITE,
                        '0,707', '0,857', '0,8'):
            self.assertIn(attendu, alerte['message'])
        self.assertNotIn('MAD', alerte['message'])

    def test_sans_kvarh_ni_cos_phi_note_seule(self):
        res = _cas_reference(kvarh_mensuels=None)
        self.assertEqual(res['statut'], 'non_evalue')
        self.assertEqual([a['code'] for a in res['alertes']],
                         ['cos_phi_non_evalue'])
        self.assertEqual(res['alertes'][0]['message'],
                         reactif.NOTE_NON_DECLARE)

    def test_bt_rien(self):
        res = _cas_reference(tension='bt')
        self.assertEqual(res, {'statut': 'sans_objet', 'par_mois': [],
                               'alertes': []})

    def test_cos_phi_declare_avec_provenance(self):
        res = _cas_reference(kvarh_mensuels=None, cos_phi_declare=0.857,
                             provenance_cos_phi={'origine': 'lead',
                                                 'detail': 'site_web',
                                                 'date': '2026-09-10'})
        # cos φ 0,857 arrondi ⇒ Q ≈ 60 040 kvarh ⇒ cos φ après ≈ 0,707.
        self.assertAlmostEqual(res['par_mois'][0]['cos_phi_apres'], 0.707,
                               delta=0.002)
        self.assertIn('site_web', res['alertes'][0]['message'])

    def test_au_dessus_du_seuil_aucune_alerte(self):
        res = _cas_reference(autoconso_mensuels=[5000.0])
        self.assertEqual(res['statut'], 'evalue')
        self.assertEqual(res['alertes'], [])


class BranchementEtudeTest(SimpleTestCase):
    def test_etude_mt_porte_l_alerte_depuis_les_registres(self):
        res = etude_ci.resoudre_entrees({'mode': 'industriel'})
        bilan = {'par_mois': [{'mois': 1, 'consommation_kwh': 100000,
                               'autoconso_kwh': 40000}]}
        alertes = etude_ci._alertes_reactif(res, 'mt', bilan,
                                            [{'kvarh': 60000}])
        self.assertEqual([a['code'] for a in alertes], ['cos_phi_apres_pv'])

    def test_cos_phi_saisi_feuille_privee_hors_entrees_resolues(self):
        res = etude_ci.resoudre_entrees({'mode': 'industriel',
                                         'cos_phi': 0.857})
        self.assertEqual(res.valeur('_cos_phi'), 0.857)
        self.assertNotIn('_cos_phi', res.entrees_resolues())
        self.assertNotIn('cos_phi', res.entrees_resolues())
        bilan = {'par_mois': [{'mois': 1, 'consommation_kwh': 100000,
                               'autoconso_kwh': 40000}]}
        alertes = etude_ci._alertes_reactif(res, 'mt', bilan, None)
        self.assertEqual([a['code'] for a in alertes], ['cos_phi_apres_pv'])

    def test_bt_aucune_alerte(self):
        res = etude_ci.resoudre_entrees({'mode': 'industriel',
                                         'cos_phi': 0.6})
        bilan = {'par_mois': [{'mois': 1, 'consommation_kwh': 100000,
                               'autoconso_kwh': 40000}]}
        self.assertEqual(etude_ci._alertes_reactif(res, 'bt', bilan, None), [])


class GardeClesPubliquesTest(SimpleTestCase):
    def _apercu_avec_alerte(self):
        with open(os.path.join(_VENTES, 'contract_samples',
                               'etude_ci_preview.json'),
                  encoding='utf-8') as fh:
            apercu = copy.deepcopy(json.load(fh)['exemple'])
        apercu['entrees_resolues']['tension'] = {'valeur': 'mt'}
        apercu['alertes'].extend(_cas_reference()['alertes'])
        return apercu

    def test_relayee_en_interne_jamais_publique(self):
        apercu = self._apercu_avec_alerte()
        bloc = eco.assembler_economie_ci(
            apercu, investissement={'ht': 900000.0, 'ttc': 1080000.0},
            mode_installation='industriel')
        relayees = [a for a in bloc['alertes_internes']
                    if a['code'] == 'cos_phi_apres_pv']
        self.assertEqual(len(relayees), 1)
        self.assertIs(relayees[0]['interne'], True)
        # Relayée TELLE QUELLE (aucun recalcul) : même message.
        self.assertEqual(relayees[0]['message'],
                         _cas_reference()['alertes'][0]['message'])
        public = json.dumps(eco.economie_ci_publique(bloc),
                            ensure_ascii=False)
        self.assertNotIn('cos_phi', public)
        self.assertNotIn('cos φ', public)

    def test_synthese_ci_sans_cos_phi(self):
        etude = self._apercu_avec_alerte()
        data = {'mode_installation': 'industriel',
                'etude': {'etude_ci': etude}}
        sortie = json.dumps(synthese_ci(data), ensure_ascii=False)
        self.assertNotIn('cos_phi', sortie)
        self.assertNotIn('cos φ', sortie)


class GardeAstTest(SimpleTestCase):
    """Une seule formule : ``reactif.py`` est PUR (aucun import Django ni
    d'app) et ni ``economie_ci`` ni ``etude_ci`` ne recalculent un cos φ."""

    def _arbre(self, *chemin):
        with open(os.path.join(_VENTES, *chemin), encoding='utf-8') as fh:
            return ast.parse(fh.read())

    def test_reactif_pur(self):
        modules = set()
        for noeud in ast.walk(self._arbre('moteur_ci', 'reactif.py')):
            if isinstance(noeud, ast.Import):
                modules.update(a.name for a in noeud.names)
            elif isinstance(noeud, ast.ImportFrom):
                modules.add(noeud.module)
        self.assertEqual(modules, {'__future__', 'math'})

    def test_aucune_seconde_formule(self):
        for chemin in (('economie_ci.py',), ('domain', 'etude_ci.py')):
            for noeud in ast.walk(self._arbre(*chemin)):
                if isinstance(noeud, ast.Attribute):
                    self.assertNotIn(noeud.attr, ('sqrt', 'acos', 'hypot'),
                                     chemin)
                if isinstance(noeud, ast.FunctionDef):
                    self.assertNotIn('cos_phi', noeud.name.replace(
                        '_alertes_reactif', ''), chemin)
