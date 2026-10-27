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
        # CMP1/CMP2 : fenêtre de tension VIDE (démarrage 600 V ≥ ce que la
        # tension maxi 700 V laisse monter) — la fenêtre 30-45 V d'avant
        # raccordait 1 module par appareil, désormais comptée dans la capacité.
        module, cat = self._avec_fiches({'n_mppt': 1, 'mppt_v_min': 600, 'mppt_v_max': 1000,
                                         'v_max_abs': 700, 'i_max_mppt_a': 30})
        r = combiner_onduleurs(35, cat, phase='tri', module=module)
        alerte = next(a for a in r['alertes'] if a['code'] == 'OND_CHAINES_NON_FAISABLES')
        self.assertEqual(alerte['niveau'], 'bloquant')

    def test_aucune_cle_prix_achat(self):
        r = combiner_onduleurs(100, self.cat, phase='tri')
        self.assertNotIn('prix_achat', repr(r))


def _module_cs7n():
    from core.electrique.types import SpecModule
    return SpecModule(vmp_v=40.4, voc_v=48.3, isc_a=18.59, imp_a=17.59, pmax_wc=710,
                      temp_coeff_voc_pct_c=-0.25)


def _spec_ond(n_mppt, v_min, v_max, v_abs, i_max, kw):
    from core.electrique.types import SpecOnduleur
    return SpecOnduleur(n_mppt=n_mppt, mppt_v_min=v_min, mppt_v_max=v_max, v_max_abs=v_abs,
                        i_max_mppt_a=i_max, ac_kw=kw, phases=3)


def _cand(pid, nom, kw, prix, spec):
    return {'produit': pid, 'nom': nom, 'kw_ac': kw, 'prix': Decimal(prix), 'triphase': True,
            'eligible_ci': True, 'motif_exclusion': None, 'spec': spec}


def _vivier_huawei():
    h = lambda n, i, kw: _spec_ond(n, 200, 1000, 1100, i, kw)  # noqa: E731
    return [_cand(1, 'Huawei 15KTL-M5', 15, '19167', h(2, 20, 15)),
            _cand(2, 'Huawei 20KTL-M5', 20, '23333', h(2, 20, 20)),
            _cand(5, 'Huawei 50KTL-M3', 50, '45833', h(4, 30, 50)),
            _cand(6, 'Huawei 100KTL', 100, '65000', h(10, 30, 100)),
            _cand(7, 'Huawei 150K-MG0', 150, '102500', h(7, 48, 150))]


def _vivier_deye():
    d = lambda kw: _spec_ond(2, 160, 650, 800, 20, kw)  # noqa: E731
    return [_cand(10, 'Deye 10K', 10, '23333', d(10)), _cand(11, 'Deye 15K', 15, '30000', d(15)),
            _cand(12, 'Deye 20K', 20, '40000', d(20))]


class ChainesCiTests(TestCase):
    """CMP1 — chaînes conçues appareil par appareil (valeurs calculées par la
    fenêtre ``fenetre_admissible`` : CS7N-710 → 6 à 21 modules sur Huawei)."""

    def test_29_modules_sur_15ktl_deux_chaines_sans_reserve(self):
        from apps.ventes.moteur_ci.chaines_ci import concevoir_chaines_ci
        r = concevoir_chaines_ci(_module_cs7n(), _vivier_huawei()[0]['spec'], 29)
        self.assertEqual(r['bloquants'], [])
        self.assertEqual(r['nb_chaines'], 2)
        self.assertEqual(sorted((e['longueur'] for e in r['entrees']), reverse=True), [15, 14])
        self.assertEqual(sum(e['nb_chaines'] * e['longueur'] for e in r['entrees']), 29)

    def test_282_modules_sur_150k_mg0_deux_chaines_par_entree(self):
        from apps.ventes.moteur_ci.chaines_ci import concevoir_chaines_ci
        module = _module_cs7n()
        r = concevoir_chaines_ci(module, _vivier_huawei()[4]['spec'], 282)
        self.assertEqual(r['bloquants'], [])
        self.assertEqual(r['nb_chaines'], 14)
        self.assertEqual(len(r['entrees']), 7)
        for e in r['entrees']:
            self.assertEqual(e['nb_chaines'], 2)
            self.assertIn(e['longueur'], (20, 21))
            self.assertLessEqual(e['nb_chaines'] * module.imp_a, 48 + 1e-9)
        self.assertEqual(sum(e['nb_chaines'] * e['longueur'] for e in r['entrees']), 282)

    def test_champ_non_raccordable_bloquant_nomme_jamais_partiel(self):
        from apps.ventes.moteur_ci.chaines_ci import concevoir_chaines_ci
        r = concevoir_chaines_ci(_module_cs7n(), _vivier_huawei()[0]['spec'], 60,
                                 nom='Huawei 15KTL-M5')
        self.assertTrue(r['bloquants'])
        self.assertIn('Huawei 15KTL-M5', r['bloquants'][0])
        self.assertEqual(r['entrees'], [])

    def test_combiner_20_kwc_tous_les_modules_cables(self):
        cat = [c for c in _vivier_huawei() if c['kw_ac'] == 20]
        r = combiner_onduleurs(20.59, cat, phase='tri', module=_module_cs7n())
        self.assertEqual(r['chaines'][0]['nb_modules'], 29)
        self.assertEqual(r['chaines'][0]['nb_chaines'], 2)
        self.assertEqual([a for a in r['alertes'] if a['niveau'] == 'bloquant'], [])


class CapaciteEntreesTests(TestCase):
    """CMP2 — la capacité d'un appareil est bornée par ses entrées."""

    def test_64_kwc_jamais_un_seul_50kw_et_tout_le_champ_raccorde(self):
        module = _module_cs7n()
        r = combiner_onduleurs(64, _vivier_huawei(), phase='tri', module=module)
        self.assertNotEqual([(x['kw_ac'], x['quantite']) for x in r['combinaison']], [(50.0, 1)])
        self.assertEqual(sum(c['nb_modules'] for c in r['chaines']), 91)
        self.assertEqual([a for a in r['alertes'] if a['niveau'] == 'bloquant'], [])
        self.assertTrue(any(h['cle'] == 'raccordement_entrees' for h in r['hypotheses']))

    def test_50ktl_porte_59_6_kwc_pas_67_5(self):
        cat = [c for c in _vivier_huawei() if c['kw_ac'] == 50]
        r = combiner_onduleurs(60, cat, phase='tri', module=_module_cs7n())
        self.assertEqual(r['combinaison'][0]['quantite'], 2)

    def test_sans_module_borne_dc_ac_seule(self):
        cat = [c for c in _vivier_huawei() if c['kw_ac'] == 50]
        r = combiner_onduleurs(60, cat, phase='tri')
        self.assertEqual(r['combinaison'][0]['quantite'], 1)


class ParalleleMaxTests(TestCase):
    """CMP3 — au plus ``max_appareils`` hybrides en parallèle."""

    def test_500_kwc_au_dela_de_10_appareils_aucune_combinaison_nommee(self):
        r = combiner_onduleurs(500, _vivier_deye(), phase='tri', module=_module_cs7n(),
                               max_appareils=10)
        self.assertIsNone(r['combinaison'])
        self.assertIn('10 appareils', r['motif'])
        self.assertTrue(any(a['code'] == 'OND_PARALLELE_MAX' for a in r['alertes']))

    def test_sous_la_borne_la_combinaison_est_rendue(self):
        r = combiner_onduleurs(100, _vivier_deye(), phase='tri', module=_module_cs7n(),
                               max_appareils=10)
        self.assertLessEqual(sum(x['quantite'] for x in r['combinaison']), 10)

    def test_sans_max_appareils_inchange(self):
        r = combiner_onduleurs(500, _vivier_deye(), phase='tri', module=_module_cs7n())
        self.assertGreater(sum(x['quantite'] for x in r['combinaison']), 10)


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


def _vivier_huawei_10_a_150():
    """Pool 10/15/20/25/50/100/150 kW, prix de vente HT (CMP1 : balayage)."""
    h = lambda n, i, kw: _spec_ond(n, 200, 1000, 1100, i, kw)  # noqa: E731
    return [_cand(1, 'Huawei 10KTL', 10, '20000', h(2, 20, 10)),
            _cand(2, 'Huawei 15KTL-M5', 15, '23000', h(2, 20, 15)),
            _cand(3, 'Huawei 20KTL-M5', 20, '28000', h(2, 20, 20)),
            _cand(4, 'Huawei 25KTL', 25, '35000', h(3, 30, 25)),
            _cand(5, 'Huawei 50KTL-M3', 50, '55000', h(4, 30, 50)),
            _cand(6, 'Huawei 100KTL', 100, '78000', h(10, 30, 100)),
            _cand(7, 'Huawei 150K-MG0', 150, '123000', h(7, 48, 150))]


class BalayageCablageTests(TestCase):
    """CMP1 — aucun kWc de 190 a 232 ne reste bloque par la decoupe."""

    def _verifier(self, kwc, vivier, module):
        r = combiner_onduleurs(kwc, vivier, phase='tri', module=module)
        attendu = int(-(-round(kwc * 1000.0, 6) // 710))
        self.assertIsNotNone(r['combinaison'], kwc)
        self.assertEqual([a['code'] for a in r['alertes']
                          if a['code'] == 'OND_CHAINES_NON_FAISABLES'], [], kwc)
        self.assertEqual(sum(c['nb_modules'] for c in r['chaines']), attendu, kwc)
        return r

    def test_balayage_190_a_232_kwc_aucun_bloquant_tous_modules_cables(self):
        vivier, module = _vivier_huawei_10_a_150(), _module_cs7n()
        t0 = time.perf_counter()
        for pas in range(1900, 2321):
            self._verifier(pas / 10.0, vivier, module)
        self.assertLess(time.perf_counter() - t0, 120)

    def test_302_modules_repartis_275_27_recables_276_26(self):
        vivier = [c for c in _vivier_huawei_10_a_150() if c['kw_ac'] in (15, 150)]
        r = self._verifier(213.8, vivier, _module_cs7n())
        self.assertEqual(sum(c['nb_modules'] for c in r['chaines']), 302)
        self.assertNotEqual(sorted(c['nb_modules'] for c in r['chaines']), [27, 275])

    def test_champ_vraiment_infaisable_reste_bloquant(self):
        # 150K seul : 275 modules (impair) = 14 chaines -> 8 entrees > 7,
        # aucune autre combinaison possible dans ce vivier.
        cat = [c for c in _vivier_huawei_10_a_150() if c['kw_ac'] == 150]
        r = combiner_onduleurs(195.25, cat, phase='tri', module=_module_cs7n(),
                               max_appareils=1)
        self.assertIsNotNone(r['combinaison'])
        self.assertTrue(any(a['code'] == 'OND_CHAINES_NON_FAISABLES'
                            and a['niveau'] == 'bloquant' for a in r['alertes']))
