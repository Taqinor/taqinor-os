"""CIQ116 — taille C&I = plus grande taille dont chaque tranche de 5 kWc se
rembourse en ≤ HORIZON_MARGINAL_PV sur l'autoconsommation HORAIRE.

Fixtures : charge = archétypes sourcés CIQ107 (bureau BDEW G1, hôtel NREL
ComStock small hotel) ; production = PVGIS vendorisé (Casablanca) ; onduleurs
= combinaison CIQ111 sur les Huawei SEEDÉS ; panneaux / structure = prix
SEEDÉS (``seed_catalogue``, TTC → HT 20 %) ; économie = valorisation CIQ204 sur
la grille ONEE BT patenté (repli officiel). Aucune base.
"""
import ast
import unittest
from decimal import Decimal
from functools import partial
from pathlib import Path

from apps.stock.management.commands.seed_catalogue import CATALOGUE, ht_at
from apps.ventes import economie_ci, tarif_ci
from apps.ventes.dimensionnement import HORIZON_MARGINAL_PV
from apps.ventes.moteur_ci.onduleurs import combiner_onduleurs
from apps.ventes.moteur_ci.taille import cout_vente_ht, dimensionner_ci, grimper_avec_regard
from apps.ventes.tests.test_ciq110_autoconso_horaire import _charge, _production
from apps.ventes.tests.test_ciq111_combinaison_onduleurs import _catalogue_huawei

CHEMIN = Path(__file__).resolve().parent.parent / 'moteur_ci' / 'taille.py'
TARIF_BT = tarif_ci.tarif_applicable({'contrat': 'bt_patente'})


def _prix_seed(sku):
    for _nom, s, _cat, ttc, *_r in CATALOGUE:
        if s == sku:
            return ht_at(ttc, Decimal('20'))
    raise KeyError(sku)


PANNEAU_WC = 710
PRIX_PANNEAU = _prix_seed('PAN-JK-710')
PRIX_STRUCTURE = _prix_seed('STR-ACIER')


def _composer(kwc, _onduleurs, *, prix_structure=PRIX_STRUCTURE):
    import math
    n = int(math.ceil(kwc * 1000 / PANNEAU_WC - 1e-9))
    return {'lignes': [
        {'role': 'panneau', 'designation': 'Panneau 710 W', 'quantite': n,
         'prix_connu': True, 'prix_unitaire_ht': str(PRIX_PANNEAU),
         'a_confirmer_visite': False},
        {'role': 'structure_ci', 'designation': 'Structure C&I', 'quantite': n,
         'prix_connu': prix_structure is not None,
         'prix_unitaire_ht': None if prix_structure is None else str(prix_structure),
         'a_confirmer_visite': False},
        {'role': 'mise_en_service_ci', 'designation': 'Mise en service', 'quantite': 1,
         'prix_connu': False, 'a_confirmer_visite': False},
    ]}


def _valoriser(charge):
    def f(bilan):
        res = economie_ci.valoriser(
            {'bilan': bilan, 'profil_charge': {'jours_types': charge},
             'entrees_resolues': {'tension': {'valeur': 'bt'}}}, TARIF_BT)
        return (res.get('economie_annee1') or {}).get('total_mad')
    return f


class TailleCITests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.prod, _ = _production()
        cls.huawei = _catalogue_huawei()

    def _taille(self, categorie, kwh_mois, **kw):
        charge = _charge(categorie, kwh_mois)
        params = dict(
            charge_jours_types=charge, production_jours_types=self.prod, tension='bt',
            combiner=partial(combiner_onduleurs, candidats=self.huawei, phase='tri'),
            composer=kw.pop('composer', _composer), valoriser=_valoriser(charge),
            taux_tva_pct=20)
        params.update(kw)
        return dimensionner_ci(**params)

    def test_hotel_et_bureau_tailles_differentes(self):
        hotel = self._taille('hotel', 6000)['taille']
        bureau = self._taille('bureau', 6000)['taille']
        self.assertIsNotNone(hotel['retenue_kwc'])
        self.assertIsNotNone(bureau['retenue_kwc'])
        self.assertNotEqual(hotel['retenue_kwc'], bureau['retenue_kwc'])

    def test_grosse_facture_hiver_independante_de_la_regle_900(self):
        # ≈ 30 000 MAD/mois d'hiver : l'ancienne règle donnait ⌊30000/900⌋×5 = 165 kWc.
        t = self._taille('bureau', 20000)['taille']
        self.assertEqual(t['raison_arret'], 'horizon_marginal')
        self.assertNotEqual(t['retenue_kwc'], 165)
        t2 = self._taille('bureau', 20400)['taille']   # même ⌊/900⌋ d'hiver
        self.assertLessEqual(t['retenue_kwc'], t2['retenue_kwc'])

    def test_grand_besoin_non_borne_par_marche_onduleur(self):
        t = self._taille('hotel', 100000)['taille']
        self.assertGreater(t['retenue_kwc'], 185)
        self.assertNotEqual(t['raison_arret'], 'onduleurs')

    def test_toit_declare_borne(self):
        bornes = {'toit': {'kwc': 30, 'source': 'surface utile déclarée (300 m²)'}}
        t = self._taille('hotel', 20000, bornes=bornes)['taille']
        self.assertEqual(t['retenue_kwc'], 30)
        self.assertEqual(t['raison_arret'], 'toit')
        self.assertEqual(t['paliers'][-1]['borne'], 'toit')

    def test_puissance_souscrite_borne(self):
        r = self._taille('hotel', 100000, puissance_souscrite_kva=80)
        t = r['taille']
        self.assertEqual(t['raison_arret'], 'puissance_souscrite')
        ac = sum(i['kw_ac'] * i['quantite'] for i in r['evaluation']['onduleurs']['combinaison'])
        self.assertLessEqual(ac, 80)
        self.assertEqual(t['bornes']['puissance_souscrite']['kva'], 80)

    def test_puissance_souscrite_inconnue_alerte_sans_borne(self):
        r = self._taille('bureau', 6000)
        self.assertIn('puissance_souscrite_inconnue', [a['code'] for a in r['alertes']])
        self.assertIsNone(r['taille']['bornes']['puissance_souscrite']['kva'])

    def test_taille_explicite_souveraine(self):
        bornes = {'toit': {'kwc': 30, 'source': 'déclaré'}}
        r = self._taille('hotel', 20000, bornes=bornes, taille_explicite_kwc=120,
                         puissance_souscrite_kva=50)
        self.assertEqual(r['taille']['retenue_kwc'], 120)
        self.assertEqual(r['taille']['raison_arret'], 'taille_explicite')
        codes = [a['code'] for a in r['alertes']]
        self.assertIn('taille_au_dela_du_toit', codes)
        self.assertIn('taille_au_dela_ps', codes)

    def test_structure_sans_prix_prix_manquants(self):
        r = self._taille('bureau', 6000, composer=partial(_composer, prix_structure=None))
        self.assertIsNone(r['taille']['retenue_kwc'])
        self.assertEqual(r['taille']['raison_arret'], 'prix_manquants')
        self.assertIn('Structure C&I', r['prix_manquants'])

    def test_poste_fixe_sans_prix_monte_quand_meme(self):
        # ADEV79 — re-scopé : seul un poste HORS rôles de taille (mise en
        # service) laisse la taille monter ; le devis automatique refuse
        # ensuite en le nommant (D-ACI-6=a, refus_devis_auto_ci).
        r = self._taille('bureau', 6000)
        self.assertIsNotNone(r['taille']['retenue_kwc'])
        self.assertIn('postes_fixes_sans_prix', [a['code'] for a in r['alertes']])
        self.assertEqual(r['taille']['statut'], 'calculee')

    # ── ADEV79 : lignes de taille sans prix, lignes à chiffrer après visite ──

    def _avec(self, ligne):
        def composer(kwc, onduleurs):
            base = _composer(kwc, onduleurs)
            base['lignes'].append(dict(ligne, quantite=ligne.get('quantite', 3)))
            return base
        return composer

    def test_structure_a_confirmer_sans_prix_prix_manquants(self):
        def composer(kwc, onduleurs):
            base = _composer(kwc, onduleurs, prix_structure=None)
            base['lignes'][1]['a_confirmer_visite'] = True
            return base
        r = self._taille('bureau', 6000, composer=composer)
        self.assertEqual(r['taille']['raison_arret'], 'prix_manquants')
        self.assertIn('Structure C&I', r['prix_manquants'])

    def test_pose_modules_sans_prix_prix_manquants(self):
        r = self._taille('bureau', 6000, composer=self._avec(
            {'role': 'pose_modules', 'designation': 'Pose des modules C&I', 'quantite': 1,
             'prix_connu': False, 'a_confirmer_visite': False}))
        self.assertEqual(r['taille']['raison_arret'], 'prix_manquants')
        self.assertIn('Pose des modules C&I', r['prix_manquants'])
        self.assertIn('Mise en service', r['postes_fixes_sans_prix'])

    def test_ligne_a_chiffrer_visite_hors_taille_statut_estimation(self):
        r = self._taille('bureau', 6000, composer=self._avec(
            {'role': 'cable_dc', 'designation': 'Câble solaire DC', 'quantite': None,
             'prix_connu': False, 'a_confirmer_visite': True, 'a_chiffrer_visite': True}))
        self.assertIsNotNone(r['taille']['retenue_kwc'])
        self.assertEqual(r['taille']['statut'], 'estimation')
        self.assertNotIn('Câble solaire DC', r['evaluation']['prix_manquants'])

    def test_palier_ttc_ramene_ht_par_la_tva_de_l_article(self):
        ligne = {'role': 'panneau', 'quantite': 10, 'prix_connu': True,
                 'prix_unitaire_ht': '999', 'prix_unitaire_ttc': '110', 'tva_pct': '10',
                 'palier': {'seuil_min': 10, 'seuil_max': None, 'mention': 'palier'}}
        cout = cout_vente_ht({'lignes': [ligne]}, {}, taux_tva_pct=20)
        self.assertEqual(cout, Decimal('1000.00'))
        sans_tva_article = cout_vente_ht({'lignes': [dict(ligne, tva_pct=None)]}, {},
                                         taux_tva_pct=10)
        self.assertEqual(sans_tva_article, Decimal('1000.00'))

    # ── ADEV78 : la vraie cause d'un arrêt « onduleurs » ou « module » ──────

    def test_aucun_onduleur_eligible_alerte_nomme_chaque_candidat(self):
        inel = [dict(c, eligible_ci=False, motif_exclusion='fiche onduleur absente')
                for c in self.huawei[:2]]
        r = self._taille('bureau', 6000, combiner=partial(
            combiner_onduleurs, candidats=inel, phase='tri'))
        self.assertIsNone(r['taille']['retenue_kwc'])
        self.assertEqual(r['taille']['raison_arret'], 'onduleurs')
        alerte = next(a for a in r['alertes'] if a['code'] == 'OND_AUCUN_CANDIDAT')
        self.assertEqual(alerte['niveau'], 'bloquant')
        self.assertTrue(alerte['message'].startswith('Aucun onduleur C&I éligible'))
        for c in inel:
            self.assertIn('%s (fiche onduleur absente)' % c['nom'], alerte['message'])
        self.assertNotIn('rentable', alerte['message'])

    def test_module_sans_pmax_arret_module_aucun_palier_a_cout_nul(self):
        def sans_panneau(kwc, onduleurs):
            lignes = [ligne for ligne in _composer(kwc, onduleurs)['lignes']
                      if ligne['role'] != 'panneau']
            return {'lignes': lignes}
        r = self._taille('bureau', 6000, composer=sans_panneau)
        self.assertIsNone(r['taille']['retenue_kwc'])
        self.assertEqual(r['taille']['raison_arret'], 'module')
        self.assertEqual(r['taille']['paliers'], [])
        self.assertIsNone(r['evaluation'])
        self.assertIn('CI_MODULE_FICHE',
                      [a['code'] for a in r['alertes'] if a['niveau'] == 'bloquant'])
        explicite = self._taille('bureau', 6000, composer=sans_panneau, taille_explicite_kwc=50)
        self.assertEqual(explicite['taille']['raison_arret'], 'module')
        self.assertIsNone(explicite['evaluation'])

    def test_palier_a_cout_nul_jamais_admis(self):
        def gratuit(kwc, onduleurs):
            return {'lignes': [dict(ligne, prix_unitaire_ht='0')
                               for ligne in _composer(kwc, onduleurs)['lignes']]}
        gratuits = [dict(c, prix='0.01') for c in self.huawei]
        r = self._taille('bureau', 6000, composer=gratuit, combiner=lambda kwc: dict(
            combiner_onduleurs(kwc, gratuits, phase='tri'), prix_vente_total_ht='0'))
        self.assertFalse(any(p['admis'] for p in r['taille']['paliers']))
        self.assertIsNone(r['taille']['retenue_kwc'])

    def test_distributeur_sans_effet(self):
        # La valeur du distributeur (onee / srm_casablanca) n'est pas une entrée du
        # moteur : deux appels identiques rendent la même taille (CAD167/Q16).
        a = self._taille('bureau', 6000)['taille']
        b = self._taille('bureau', 6000)['taille']
        self.assertEqual(a, b)

    def test_payback_global_dans_horizon(self):
        r = self._taille('bureau', 6000)
        e = r['evaluation']
        self.assertLessEqual(e['cout'] / e['economie'], HORIZON_MARGINAL_PV)
        admis = [p for p in r['taille']['paliers'] if p['admis']]
        self.assertTrue(all(p['ratio_marginal_annees'] <= HORIZON_MARGINAL_PV for p in admis))
        self.assertEqual(admis[-1]['kwc'], r['taille']['retenue_kwc'])


class SautOnduleurTests(unittest.TestCase):
    """Fondateur 26/10/2026 — boulangerie : 30 → 35 kWc coûte +41 281 HT (onduleur
    25 → 50 kW) pour +3 585 MAD/an (11,5 ans seul) ; 30 → 40 ensemble se
    rembourse en ~8,6 ans ⇒ 40 kWc retenu, jamais bloqué au saut d'onduleur."""

    @staticmethod
    def _cumul(marges):
        cout = eco = 0
        sortie = []
        for kwc, d_cout, d_eco in marges:
            cout, eco = cout + d_cout, eco + d_eco
            sortie.append({'kwc': kwc, 'cout': cout, 'eco': eco})
        return sortie

    def _monter(self, marges):
        paliers = self._cumul(marges)
        return grimper_avec_regard(paliers[0], paliers[1:], HORIZON_MARGINAL_PV,
                                   lambda e: e['cout'], lambda e: e['eco'])['kwc']

    def test_palier_cher_seul_garde_si_le_groupe_se_rembourse(self):
        self.assertEqual(self._monter([
            (25, 122982, 54466), (30, 18974, 5393), (35, 41281, 3585),
            (40, 12000, 2607)]), 40)

    def test_groupe_hors_horizon_arret_au_dernier_palier_rentable(self):
        self.assertEqual(self._monter([
            (25, 122982, 54466), (30, 18974, 5393), (35, 41281, 1000),
            (40, 30000, 500)]), 30)


def _hybrides_bt():
    """Deye SG05LP3 basse tension triphasés aux prix SEEDÉS (port batterie de
    la fiche seedée ; 10 kW : borne non publiée ⇒ aucune)."""
    sortie = []
    for i, (kw, sku, port) in enumerate(((10, 'OND-H-DEY-10T', None), (15, 'OND-H-DEY-15T', 14.34),
                                         (20, 'OND-H-DEY-20T', 17.92))):
        sortie.append({'produit': 900 + i, 'nom': 'Onduleur hybride Deye %d kW triphasé' % kw,
                       'kw_ac': kw, 'prix': _prix_seed(sku), 'triphase': True, 'eligible_ci': True,
                       'motif_exclusion': None, 'plage_batterie_v': [40, 60],
                       'bat_max_charge_kw': port})
    return sortie


def _batterie(pid, nom, utile, prix, charge_kw):
    return {'produit': pid, 'nom': nom, 'kwh_utile': utile, 'v_nominal': 51.2, 'prix': prix,
            'max_modules': None, 'max_charge_kw': charge_kw, 'rendement': 0.98,
            'element': {'id': pid, 'nom': nom, 'prix_connu': prix is not None,
                        'prix_vente_ht': prix}}


#: Dyness 5 / 10 kWh : fiches et prix SEEDÉS ; PowerBrick SC 16 kWh : fiche
#: fondateur (15,27 kWh utiles, 7,17 kW), prix de TEST (aucun prix publié).
BATTERIES = [
    _batterie(950, 'Batterie Dyness 5 kWh', 4.6, _prix_seed('BAT-DEY-5'), 3.84),
    _batterie(951, 'Batterie Dyness 10 kWh', 9.22, _prix_seed('BAT-DEY-10'), 5.12),
    _batterie(952, 'Batterie Dyness PowerBrick SC 16 kWh', 15.27, Decimal('40000'), 7.17),
]


class OptionAvecBatterieTests(unittest.TestCase):
    """Fondateur 26/10/2026 — l'option « avec batterie » C&I : hybrides BT à la
    place des string, banque homogène sur le soir/nuit d'un jour moyen, champ
    porté au remplissage (QJR612) puis par la règle des 10 ans."""

    @classmethod
    def setUpClass(cls):
        from apps.ventes.etude_horaire import simuler_batterie_jour
        cls.simuler = staticmethod(simuler_batterie_jour)
        cls.prod, _ = _production()
        cls.charge = _charge('boulangerie', 6000)
        cls.sans = dimensionner_ci(
            charge_jours_types=cls.charge, production_jours_types=cls.prod, tension='bt',
            combiner=partial(combiner_onduleurs, candidats=_catalogue_huawei(), phase='tri'),
            composer=_composer, valoriser=_valoriser(cls.charge), taux_tva_pct=20)['evaluation']

    def _avec(self, batteries=BATTERIES, **kw):
        from apps.ventes.moteur_ci.batterie import dimensionner_option_avec
        hybrides = _hybrides_bt()
        params = dict(
            kwc_depart=self.sans['kwc'], pmax_wc=PANNEAU_WC, charge=self.charge,
            production=self.prod, tension='bt', revente_choisie=False,
            combiner=partial(combiner_onduleurs, candidats=hybrides, phase='tri'),
            composer=_composer, valoriser=_valoriser(self.charge), batteries=batteries,
            simuler=self.simuler, hybrides=hybrides, taux_tva_pct=20)
        params.update(kw)
        return dimensionner_option_avec(**params)

    def test_boulangerie_hybrides_bt_banque_homogene_toujours_pleine(self):
        from apps.ventes.moteur_ci.batterie import besoin_nocturne_kwh
        e = self._avec()['evaluation']
        self.assertIsNotNone(e)
        self.assertTrue({x['produit'] for x in e['onduleurs']['combinaison']} <= {900, 901, 902})
        bat = e['batterie']
        self.assertIn(bat['produit'], (950, 951, 952))
        besoin = besoin_nocturne_kwh(self.charge, self.sans['bilan'])
        self.assertAlmostEqual(bat['besoin_nocturne_kwh'], round(besoin, 2), places=2)
        self.assertGreaterEqual(bat['capacite_utile_kwh'] * bat['rendement'], besoin - 1e-6)
        self.assertTrue(bat['se_remplit_tous_les_jours'])
        self.assertGreaterEqual(e['kwc'], self.sans['kwc'])
        self.assertGreater(e['bilan']['batterie']['restitue_kwh_an'], 0)
        self.assertGreater(e['bilan']['autoconso_kwh'], self.sans['bilan']['autoconso_kwh'])
        # Batterie au prix de VENTE dans le coût de l'option, jamais un achat.
        ligne = [li for li in e['composition']['lignes'] if li['role'] == 'batterie_ci'][0]
        self.assertEqual(ligne['quantite'], bat['quantite'])
        self.assertTrue(ligne['prix_connu'])

    def test_banque_le_moins_de_modules_puis_la_moins_chere(self):
        from apps.ventes.moteur_ci.batterie import choisir_banque
        banque = choisir_banque(BATTERIES, 30.0)
        self.assertEqual((banque['produit'], banque['quantite']), (952, 3))
        # Même nombre de modules (un seul) : la banque la moins chère.
        petites = [b for b in BATTERIES if b['produit'] in (950, 951)]
        self.assertEqual(choisir_banque(petites, 4.0)['produit'], 950)
        petites = [dict(b, prix=Decimal('1')) if b['produit'] == 951 else b for b in petites]
        self.assertEqual(choisir_banque(petites, 4.0)['produit'], 951)

    def test_aucune_batterie_tarifee_motif_et_prix_nommes(self):
        sans_prix = [dict(b, prix=None) for b in BATTERIES]
        r = self._avec(batteries=sans_prix)
        self.assertIsNone(r['evaluation'])
        self.assertIn('Batterie Dyness 10 kWh', r['prix_a_renseigner'])

    def test_toit_borne_banque_reduite_nommee(self):
        r = self._avec(kwc_max=self.sans['kwc'])
        e = r['evaluation']
        self.assertIsNotNone(e)
        import math
        n_sans = math.ceil(self.sans['kwc'] * 1000 / PANNEAU_WC - 1e-9)
        self.assertAlmostEqual(e['kwc'], n_sans * PANNEAU_WC / 1000, places=6)
        self.assertTrue(e['batterie']['reduite'])
        self.assertTrue(e['batterie']['se_remplit_tous_les_jours'])
        self.assertEqual([a['code'] for a in r['alertes']], ['BATTERIE_REDUITE_AU_TOIT'])

    def test_puissance_souscrite_borne_les_hybrides(self):
        e = self._avec(ps_kva=25)['evaluation']
        self.assertIsNotNone(e)
        self.assertLessEqual(e['puissance_ac'], 25 + 1e-9)

    def test_regle_10_ans_au_dela_du_remplissage(self):
        from apps.ventes.moteur_ci.batterie import monter_regle_10_ans
        # n → kWc = n × 710 Wc ; coût 1 000 MAD/kWc ; économie 300 MAD/kWc
        # jusqu'à 40 kWc, puis 50 MAD/kWc (20 ans par palier) : arrêt à 40.

        def evaluer(n):
            kwc = n * PANNEAU_WC / 1000.0
            eco = 300 * min(kwc, 40) + 50 * max(0.0, kwc - 40)
            return {'kwc': kwc, 'cout': 1000 * kwc, 'economie': eco}
        retenu = monter_regle_10_ans(29, 200, PANNEAU_WC, evaluer)
        self.assertLessEqual(abs(retenu['kwc'] - 40), PANNEAU_WC / 1000.0)
        self.assertIsNone(monter_regle_10_ans(29, 200, PANNEAU_WC, lambda n: None))


class GardeAstTests(unittest.TestCase):
    def test_aucune_regle_900_ni_taux_fixe(self):
        source = CHEMIN.read_text(encoding='utf-8')
        arbre = ast.parse(source)
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Constant) and noeud.value in (900, 900.0):
                self.fail('règle « facture ÷ 900 × 5 » réintroduite')
            if isinstance(noeud, ast.ImportFrom):
                self.assertTrue((noeud.module or '').startswith(
                    ('apps.ventes.dimensionnement', 'apps.ventes.moteur_ci', 'decimal')),
                    noeud.module)
            elif isinstance(noeud, ast.Constant) and isinstance(noeud.value, float):
                self.assertFalse(0 < noeud.value < 1 and noeud.value > 1e-6, noeud.value)


if __name__ == '__main__':
    unittest.main()
