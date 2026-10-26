"""CIQ111 — combinaison d'onduleurs C&I au coût de vente minimal.

Catalogue = les onduleurs réseau Huawei SEEDÉS (``seed_catalogue.CATALOGUE``,
prix TTC du fondateur → HT 20 %), lus dans la table du seeder (jamais
recopiés). Module PUR : aucun Django, aucune base.
"""
import ast
import time
from decimal import Decimal
from pathlib import Path
from unittest import TestCase

from apps.stock.management.commands.seed_catalogue import CATALOGUE, ht_at
from apps.ventes.moteur_ci.onduleurs import combiner_onduleurs
from core.electrique.onduleurs import bornes_dc_ac

CHEMIN = (Path(__file__).resolve().parent.parent / 'moteur_ci'
          / 'onduleurs.py')


def _catalogue_huawei():
    out = []
    for i, (nom, sku, _cat, ttc, _achat, _q, _s) in enumerate(CATALOGUE):
        if not sku.startswith('OND-R-HUA-'):
            continue
        kw = float(sku.split('-')[3][:-1])
        out.append({
            'produit': i + 1, 'nom': nom, 'kw_ac': kw,
            'prix': ht_at(ttc, Decimal('20')),
            'triphase': sku.endswith('T'), 'eligible_ci': True,
            'motif_exclusion': None,
        })
    return out


def _prix(cat, kw):
    return next(c['prix'] for c in cat if c['kw_ac'] == kw and c['triphase'])


def _cout(resultat, cat):
    par_id = {c['produit']: c['prix'] for c in cat}
    return sum(par_id[x['produit']] * x['quantite']
               for x in resultat['combinaison'])


class CombinaisonTests(TestCase):
    def setUp(self):
        self.cat = _catalogue_huawei()
        self.bornes = bornes_dc_ac(None)

    def test_190_kwc_moins_cher_que_deux_150_et_borne_haute(self):
        r = combiner_onduleurs(190, self.cat, phase='tri')
        self.assertIsNotNone(r['combinaison'])
        self.assertLessEqual(_cout(r, self.cat), 2 * _prix(self.cat, 150))
        ac = sum(x['kw_ac'] * x['quantite'] for x in r['combinaison'])
        self.assertLessEqual(190 / ac, self.bornes.borne_usuelle.valeur + 1e-9)
        self.assertEqual(r['ratio_dc_ac']['bornes']['source_haute'],
                         self.bornes.borne_usuelle.source)

    def test_35_kwc_au_plus_le_prix_d_un_50(self):
        r = combiner_onduleurs(35, self.cat, phase='tri')
        self.assertLessEqual(_cout(r, self.cat), _prix(self.cat, 50))
        self.assertEqual(Decimal(r['prix_vente_total_ht']),
                         _cout(r, self.cat).quantize(Decimal('0.01')))

    def test_le_moins_d_onduleurs_d_abord(self):
        # Fondateur 26/10/2026 (boulangerie 40 kWc) : 1 × 50 kW, jamais 2 × 15.
        r = combiner_onduleurs(40, self.cat, phase='tri')
        self.assertEqual([(x['kw_ac'], x['quantite']) for x in r['combinaison']],
                         [(50.0, 1)])

    def test_puissance_souscrite_jamais_depassee_si_evitable(self):
        r = combiner_onduleurs(70, self.cat, phase='tri', ac_max_kw=60)
        ac = sum(x['kw_ac'] * x['quantite'] for x in r['combinaison'])
        self.assertLessEqual(ac, 60)
        self.assertEqual(sum(x['quantite'] for x in r['combinaison']), 2)

    def test_fiche_incomplete_jamais_retenue_et_nommee(self):
        cat = [dict(c) for c in self.cat]
        for c in cat:
            if c['kw_ac'] == 150:
                c['eligible_ci'] = False
                c['motif_exclusion'] = ('fiche incomplète : courant maxi par '
                                        'MPPT (A)')
        r = combiner_onduleurs(190, cat, phase='tri')
        ids_150 = {c['produit'] for c in cat if c['kw_ac'] == 150}
        self.assertFalse(ids_150 & {x['produit'] for x in r['combinaison']})
        exclus = {e['produit']: e['motif'] for e in r['exclus']}
        for pid in ids_150:
            self.assertIn('courant maxi par MPPT', exclus[pid])

    def test_sans_prix_jamais_choisi(self):
        cat = [dict(c) for c in self.cat]
        for c in cat:
            c['prix'] = None
        r = combiner_onduleurs(50, cat, phase='tri')
        self.assertIsNone(r['combinaison'])
        self.assertTrue(r['motif'])

    def test_client_mono_sans_onduleur_mono_bloquant(self):
        cat = [c for c in self.cat if c['triphase']]
        r = combiner_onduleurs(20, cat, phase='mono')
        self.assertIsNone(r['combinaison'])
        self.assertIn('monophasé', r['motif'])
        self.assertTrue(any(a['niveau'] == 'bloquant' for a in r['alertes']))

    def test_client_mono_ne_recoit_que_du_mono(self):
        r = combiner_onduleurs(12, self.cat, phase='mono')
        par_id = {c['produit']: c for c in self.cat}
        for x in r['combinaison']:
            self.assertFalse(par_id[x['produit']]['triphase'])

    def test_phase_par_role_ci_et_phases_publiees(self):
        # ADEV86 (D-ACI-3=b) — les candidats du catalogue C&I portent leur
        # rôle et leur phase publiée : mono ⇒ seuls les monophasés, tri ⇒
        # seuls les triphasés.
        cat = []
        for source in self.cat:
            tri = source['triphase']
            c = {k: v for k, v in source.items() if k != 'triphase'}
            c['role_ci'] = 'onduleur_string_tri' if tri else 'onduleur_string_mono'
            c['phases'] = 3 if tri else 1
            cat.append(c)
        par_id = {c['produit']: c for c in cat}
        r = combiner_onduleurs(12, cat, phase='mono')
        self.assertTrue(r['combinaison'])
        for x in r['combinaison']:
            self.assertEqual(par_id[x['produit']]['role_ci'], 'onduleur_string_mono')
        r = combiner_onduleurs(60, cat, phase='tri')
        self.assertTrue(r['combinaison'])
        for x in r['combinaison']:
            self.assertEqual(par_id[x['produit']]['role_ci'], 'onduleur_string_tri')
        sans_mono = [c for c in cat if c['role_ci'] == 'onduleur_string_tri']
        r = combiner_onduleurs(12, sans_mono, phase='mono')
        self.assertIsNone(r['combinaison'])
        self.assertIn('aucun onduleur C&I monophasé éligible', r['motif'])

    def test_phase_inconnue_alerte(self):
        r = combiner_onduleurs(30, self.cat, phase='inconnu')
        self.assertTrue(any(a['code'] == 'OND_RACCORDEMENT_A_CONFIRMER'
                            for a in r['alertes']))

    def test_dc_max_publie_bloque(self):
        cat = [dict(c) for c in self.cat if c['kw_ac'] == 50]
        cat[0]['dc_max_kwc'] = 55.0
        r = combiner_onduleurs(60, cat, phase='tri')
        self.assertEqual(r['combinaison'][0]['quantite'], 2)

    def test_deterministe(self):
        a = combiner_onduleurs(330, self.cat, phase='tri')
        b = combiner_onduleurs(330, list(reversed(self.cat)), phase='tri')
        self.assertEqual(a['combinaison'], b['combinaison'])

    def test_aucune_taille_bornee_par_la_marche(self):
        r = combiner_onduleurs(830, self.cat, phase='tri')
        ac = sum(x['kw_ac'] * x['quantite'] for x in r['combinaison'])
        self.assertGreaterEqual(ac * self.bornes.borne_usuelle.valeur, 830)

    def test_un_mwc_en_moins_d_une_seconde(self):
        debut = time.perf_counter()
        r = combiner_onduleurs(1000, self.cat, phase='tri')
        self.assertLess(time.perf_counter() - debut, 1.0)
        self.assertIsNotNone(r['combinaison'])

    def test_chaines_a_verifier_sans_fiches(self):
        r = combiner_onduleurs(35, self.cat, phase='tri')
        self.assertIsNone(r['chaines'])
        self.assertTrue(any(a['code'] == 'OND_CHAINES_A_VERIFIER'
                            for a in r['alertes']))

    def _avec_fiches(self, onduleur):
        from apps.calepinage.services.chaines import specs_module, specs_onduleur
        module = specs_module({'vmp_v': 40, 'voc_v': 48, 'isc_a': 18, 'imp_a': 17,
                               'pmax_wc': 710}, 'Panneau 710W')[0]
        spec = specs_onduleur(dict(onduleur, ac_kw=50, phases=3), 'Onduleur 50kW')[0]
        cat = [dict(c, spec=spec) for c in self.cat if c['kw_ac'] == 50 and c['triphase']]
        return module, cat

    def test_chaines_rendues_avec_module_et_fiches(self):
        # ADEV87 — module + fiche de chaque candidat ⇒ chaînes conçues.
        module, cat = self._avec_fiches({'n_mppt': 4, 'mppt_v_min': 200, 'mppt_v_max': 1000,
                                         'v_max_abs': 1100, 'i_max_mppt_a': 30})
        r = combiner_onduleurs(35, cat, phase='tri', module=module)
        self.assertTrue(r['chaines'])
        self.assertGreater(sum(c['nb_chaines'] for c in r['chaines']), 0)
        self.assertEqual(sum(c['nb_modules'] for c in r['chaines']), 50)
        codes = [a['code'] for a in r['alertes']]
        self.assertNotIn('OND_CHAINES_A_VERIFIER', codes)
        self.assertNotIn('OND_CHAINES_NON_FAISABLES', codes)

    def test_chaines_infaisables_bloquant_nomme(self):
        module, cat = self._avec_fiches({'n_mppt': 1, 'mppt_v_min': 30, 'mppt_v_max': 45,
                                         'v_max_abs': 45, 'i_max_mppt_a': 30})
        r = combiner_onduleurs(35, cat, phase='tri', module=module)
        alerte = next(a for a in r['alertes'] if a['code'] == 'OND_CHAINES_NON_FAISABLES')
        self.assertEqual(alerte['niveau'], 'bloquant')

    def test_aucune_cle_prix_achat(self):
        r = combiner_onduleurs(100, self.cat, phase='tri')
        self.assertNotIn('prix_achat', repr(r))


class GardeAstTests(TestCase):
    def test_module_pur(self):
        arbre = ast.parse(CHEMIN.read_text(encoding='utf-8'))
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.ImportFrom):
                mod = noeud.module or ''
            elif isinstance(noeud, ast.Import):
                mod = noeud.names[0].name
            else:
                continue
            self.assertFalse(mod.startswith(('django', 'apps', 'rest_framework')),
                             mod)
