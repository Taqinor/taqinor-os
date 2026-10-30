"""CIQ116 — taille C&I = plus grande taille dont chaque tranche de 5 kWc se
rembourse en ≤ HORIZON_MARGINAL_CI (horizon C&I unique, fondateur 30/10/2026) sur l'autoconsommation HORAIRE.

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
from apps.ventes.moteur_ci.charge import courbe_declaree
from apps.ventes.moteur_ci.onduleurs import combiner_onduleurs
from apps.ventes.moteur_ci.taille import (
    HORIZON_MARGINAL_CI, cout_vente_ht, dimensionner_ci, grimper_avec_regard,
)
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
#: Horizon EXPLICITE des tests du MÉCANISME ``grimper_avec_regard`` (saut
#: d'onduleur, fenêtre de regard CLD8), calibrés sur 10 ans ; le moteur C&I
#: lui passe ``HORIZON_MARGINAL_CI`` (une constante, valeur à trancher).
HORIZON_REGARD = 10
#: Horizon C&I courant, lu — jamais recopié — par les tests ci-dessous.
H = HORIZON_MARGINAL_CI
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
            taux_tva_pct=20, pmax_wc=PANNEAU_WC)
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
        # CLD9 — toit exprimé en panneaux ENTIERS (43 × 710 Wc = 30,53 kWc) :
        # le palier 30 pose 43 panneaux et tient ; le palier 35 (50 panneaux)
        # le dépasse.
        bornes = {'toit': {'kwc': 30.53, 'source': 'surface utile déclarée (300 m²)'}}
        t = self._taille('hotel', 20000, bornes=bornes)['taille']
        self.assertEqual(t['retenue_kwc'], 30.53)
        self.assertEqual(t['nb_panneaux'], 43)
        self.assertEqual(t['raison_arret'], 'toit')
        self.assertEqual(t['paliers'][-1]['borne'], 'toit')

    def test_toit_non_multiple_garde_le_palier_en_panneaux_entiers(self):
        # CLD9 (R4) — toit de 30,00 kWc : le palier 30 pose 42 panneaux (29,82)
        # au lieu d'être refusé pour 0,53 kWc.
        bornes = {'toit': {'kwc': 30.0, 'source': 'surface utile déclarée'}}
        t = self._taille('hotel', 20000, bornes=bornes)['taille']
        self.assertEqual(t['nb_panneaux'], 42)
        self.assertAlmostEqual(t['retenue_kwc'], 29.82, places=2)
        self.assertEqual(t['raison_arret'], 'toit')

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

    def test_unite_de_la_puissance_ac_comparee_a_la_ps(self):
        # CLD10 — S max non publiée (Huawei seedés) : la puissance comparée à
        # la PS est en kW AC, jamais libellée « kVA » ; publiée : en kVA.
        r = self._taille('hotel', 20000, taille_explicite_kwc=120, puissance_souscrite_kva=50)
        msg = next(a['message'] for a in r['alertes'] if a['code'] == 'taille_au_dela_ps')
        self.assertIn('kW AC', msg)
        self.assertNotIn('kVA au-delà', msg)
        self.assertEqual(r['evaluation']['unite_puissance_ac'], 'kW AC')

        def avec_smax(kwc):
            o = combiner_onduleurs(kwc, self.huawei, phase='tri')
            for item in o.get('combinaison') or []:
                item['s_max_kva'] = item['kw_ac'] * 1.1
            return o
        r = self._taille('hotel', 20000, taille_explicite_kwc=120, puissance_souscrite_kva=50,
                         combiner=avec_smax)
        msg = next(a['message'] for a in r['alertes'] if a['code'] == 'taille_au_dela_ps')
        self.assertIn('kVA au-delà', msg)
        self.assertEqual(r['evaluation']['unite_puissance_ac'], 'kVA')

    def test_injection_au_dela_ps_en_kw(self):
        # CLD10 — le surplus horaire est une énergie par heure : une puissance
        # ACTIVE (kW), comparée aux kVA souscrits.
        from apps.ventes.moteur_ci.taille import _alertes_injection
        a = _alertes_injection({'bilan': {'horaire': [{'surplus_kwh': [12.0, 30.0]}]}}, 20.0, True)
        self.assertEqual(len(a), 1)
        self.assertIn('30.0 kW injectés', a[0]['message'])
        self.assertIn('20.0 kVA souscrits', a[0]['message'])

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

    def test_prix_manquants_au_dela_garde_les_paliers_chiffres(self):
        # CLD12 — la structure n'a de prix que jusqu'à 16 kWc : le palier 20
        # n'est plus chiffrable, les paliers 5-15 restent, la taille se
        # calcule dessus ; alerte INTERNE nommée (palier + articles).
        def composer(kwc, onduleurs):
            return _composer(kwc, onduleurs,
                             prix_structure=PRIX_STRUCTURE if kwc <= 16 else None)
        r = self._taille('bureau', 6000, composer=composer)
        t = r['taille']
        self.assertIsNotNone(t['retenue_kwc'])
        self.assertLessEqual(t['retenue_kwc'], 16)
        self.assertEqual([p['kwc'] for p in t['paliers']], [5, 10, 15])
        self.assertNotIn('prix_manquants', [a['code'] for a in r['alertes']])
        alerte = next(a for a in r['alertes'] if a['code'] == 'prix_manquants_au_dela')
        self.assertTrue(alerte['interne'])
        self.assertNotEqual(alerte['niveau'], 'bloquant')
        self.assertIn('20 kWc', alerte['message'])
        self.assertIn('Structure C&I', alerte['message'])
        self.assertNotIn('prix_manquants', r)

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
        self.assertLessEqual(e['cout'] / e['economie'], HORIZON_MARGINAL_CI)
        self.assertEqual(r['taille']['horizon_marginal_annees'], HORIZON_MARGINAL_CI)
        admis = [p for p in r['taille']['paliers'] if p['admis']]
        self.assertTrue(all(p['ratio_marginal_annees'] <= HORIZON_MARGINAL_CI for p in admis))
        # CLD9 — le dernier palier admis (clé ``kwc`` = palier) est celui dont
        # les panneaux entiers donnent la taille retenue (kWc POSÉ).
        import math
        t = r['taille']
        self.assertEqual(math.ceil(admis[-1]['kwc'] * 1000 / PANNEAU_WC - 1e-9), t['nb_panneaux'])
        self.assertAlmostEqual(t['retenue_kwc'], t['nb_panneaux'] * PANNEAU_WC / 1000, places=6)

    def test_bilan_et_onduleurs_au_kwc_pose(self):
        # CLD9 — le bilan, la combinaison et la borne sont calculés au kWc
        # réellement posé (panneaux entiers), comme la taille saisie (CAD177).
        from apps.ventes.moteur_ci.autoconso import bilan_horaire
        charge = _charge('bureau', 6000)
        vus = []

        def combiner(kwc):
            vus.append(kwc)
            return combiner_onduleurs(kwc, self.huawei, phase='tri')
        r = self._taille('bureau', 6000, combiner=combiner)
        t, e = r['taille'], r['evaluation']
        pose = t['nb_panneaux'] * PANNEAU_WC / 1000
        self.assertNotEqual(pose % 5, 0)
        self.assertAlmostEqual(t['retenue_kwc'], pose, places=6)
        self.assertAlmostEqual(e['kwc'], pose, places=6)
        attendu, _ = bilan_horaire(charge, self.prod, pose, tension='bt', revente_choisie=False)
        self.assertAlmostEqual(e['bilan']['production_kwh'], attendu['production_kwh'], places=3)
        self.assertTrue(all(abs(k * 1000 / PANNEAU_WC - round(k * 1000 / PANNEAU_WC)) < 1e-6
                            for k in vus))
        self.assertTrue(all(p['kwc'] % 5 == 0 for p in t['paliers']))

    def test_pmax_lue_sur_la_ligne_panneau(self):
        # CLD9 — sans ``pmax_wc`` injectée, la Pmax portée par la ligne
        # panneau suffit : même taille posée.
        def composer(kwc, onduleurs):
            base = _composer(kwc, onduleurs)
            base['lignes'][0]['pmax_wc'] = PANNEAU_WC
            return base
        avec = self._taille('bureau', 6000)['taille']
        ligne = self._taille('bureau', 6000, composer=composer, pmax_wc=None)['taille']
        self.assertEqual(ligne['retenue_kwc'], avec['retenue_kwc'])
        self.assertEqual(ligne['nb_panneaux'], avec['nb_panneaux'])


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
        return grimper_avec_regard(paliers[0], paliers[1:], HORIZON_REGARD,
                                   lambda e: e['cout'], lambda e: e['eco'])['kwc']

    def test_palier_cher_seul_garde_si_le_groupe_se_rembourse(self):
        self.assertEqual(self._monter([
            (25, 122982, 54466), (30, 18974, 5393), (35, 41281, 3585),
            (40, 12000, 2607)]), 40)

    def test_groupe_hors_horizon_arret_au_dernier_palier_rentable(self):
        self.assertEqual(self._monter([
            (25, 122982, 54466), (30, 18974, 5393), (35, 41281, 1000),
            (40, 30000, 500)]), 30)

    # ── CLD8 : fenêtre de regard bornée par la physique, pas par un nombre ──

    @staticmethod
    def _ond(produit, kw_ac=50.0, quantite=1):
        return {'combinaison': [{'produit': produit, 'kw_ac': kw_ac, 'quantite': quantite}],
                'ratio_dc_ac': {'bornes': {'haute': 1.35}}}

    def test_saut_amorti_au_dela_de_4_paliers_garde(self):
        # Départ 100 kWc (1 × 50 kW) ; 105 = saut vers 2 × 50 kW (+60 000 HT
        # pour +500/an) ; puis des paliers ORDINAIRES (même combinaison) à
        # 5 000 HT pour 1 000/an : le groupe 100 → 135 se rembourse en
        # 90 000 / 7 500 = 12 ans (non), 100 → 140 = 95 000 / 8 500 ≈ 11,2,
        # … 100 → 160 = 115 000 / 12 500 = 9,2 ans ≤ 10 : gardé jusqu'à 160
        # (plafond ⌈50 × 1,35 / 5⌉ = 14 paliers ; l'ancienne fenêtre de 4
        # restait à 100).
        cout, eco = 100000.0, 30000.0
        paliers = [{'kwc': 100, 'cout': cout, 'eco': eco, 'onduleurs': self._ond(1)}]
        cout, eco = cout + 60000, eco + 500
        paliers.append({'kwc': 105, 'cout': cout, 'eco': eco, 'onduleurs': self._ond(1, quantite=2)})
        for kwc in range(110, 165, 5):
            cout, eco = cout + 5000, eco + 1000
            paliers.append({'kwc': kwc, 'cout': cout, 'eco': eco,
                            'onduleurs': self._ond(1, quantite=2)})
        retenu = grimper_avec_regard(paliers[0], paliers[1:], HORIZON_REGARD,
                                     lambda e: e['cout'], lambda e: e['eco'])
        self.assertEqual(retenu['kwc'], 160)

    def test_regard_arrete_au_palier_ordinaire_hors_horizon(self):
        # Même saut, mais les paliers ordinaires sont à 11 ans SEULS : le
        # regard s'arrête au premier d'entre eux passé le plancher (4), jamais
        # plus loin — rendements décroissants, aucun groupe à sauver.
        cout, eco = 100000.0, 30000.0
        paliers = [{'kwc': 100, 'cout': cout, 'eco': eco, 'onduleurs': self._ond(1)}]
        cout, eco = cout + 60000, eco + 500
        paliers.append({'kwc': 105, 'cout': cout, 'eco': eco, 'onduleurs': self._ond(1, quantite=2)})
        for kwc in range(110, 200, 5):
            cout, eco = cout + 11000, eco + 1000
            paliers.append({'kwc': kwc, 'cout': cout, 'eco': eco,
                            'onduleurs': self._ond(1, quantite=2)})
        vus = []

        def cout_vu(e):
            vus.append(e['kwc'])
            return e['cout']
        retenu = grimper_avec_regard(paliers[0], paliers[1:], HORIZON_REGARD,
                                     cout_vu, lambda e: e['eco'])
        self.assertEqual(retenu['kwc'], 100)
        self.assertLessEqual(max(vus), 100 + 5 * 4)


class BalayageBorneTests(unittest.TestCase):
    """CLD8 — une combinaison d'onduleurs DIFFÉRENTE à chaque palier (aucun
    palier ordinaire) et des pas à 11 ans : le balayage s'arrête au plafond
    ⌈kW AC du plus gros onduleur × borne haute DC/AC ÷ PAS_KWC⌉, jamais à
    ``MAX_PAS``."""

    def _balayer(self, kw_ac):
        from unittest import mock
        from apps.ventes.moteur_ci import taille as T
        vus = []

        def evaluer(kwc, **_kw):
            rang = int(kwc // T.PAS_KWC)
            vus.append(kwc)
            cout = 10.0 + 11.0 * (rang - 1)
            eco = 10.0 + 1.0 * (rang - 1)
            return {'sans_panneau': False, 'kwc': kwc, 'composition': {'lignes': []},
                    'onduleurs': {'combinaison': [{'produit': rang, 'kw_ac': kw_ac,
                                                   'quantite': 1}],
                                  'ratio_dc_ac': {'bornes': {'haute': 1.35}}},
                    'bilan': {'taux_couverture': 0.5, 'horaire': []}, 'alertes_bilan': [],
                    'economie': eco, 'cout': cout, 'puissance_ac': kw_ac,
                    'prix_manquants': [], 'postes_fixes_sans_prix': []}
        with mock.patch.object(T, '_evaluer', evaluer):
            r = dimensionner_ci(
                charge_jours_types=[{'nb_jours': 365, 'charge_kwh': [1.0] * 24}],
                production_jours_types=[{'nb_jours': 365}], tension='bt',
                combiner=None, composer=None, valoriser=None)
        return r, vus

    def test_combinaison_differente_a_chaque_palier_balayage_borne(self):
        r, vus = self._balayer(100.0)
        self.assertEqual(r['taille']['retenue_kwc'], 5)
        # ⌈100 × 1,35 / 5⌉ = 27 paliers regardés après le dernier admis.
        self.assertEqual(len(vus), 1 + 27)

    def test_plancher_quatre_paliers(self):
        r, vus = self._balayer(5.0)    # ⌈5 × 1,35 / 5⌉ = 2 < plancher 4
        self.assertEqual(r['taille']['retenue_kwc'], 5)
        self.assertEqual(len(vus), 1 + 4)

    def test_garde_horizon_sur_le_payback_du_depart(self):
        # CLD11 — meilleur payback H − 0,1 an (5 kWc) mais départ départagé à
        # H + 0,1 (10 kWc, meilleure couverture) : le départ ne tient pas
        # dans l'horizon C&I ⇒ aucune montée (15 kWc à H ans marginal
        # refusé), alerte citant H + 0,1.
        from unittest import mock
        from apps.ventes.moteur_ci import taille as T
        c15 = 20 * (H + 0.1) + 5 * H
        table = {5: (10 * (H - 0.1), 10.0, 0.3), 10: (20 * (H + 0.1), 20.0, 0.5),
                 15: (c15, 25.0, 0.4)}

        def evaluer(kwc, **_kw):
            cout, eco, couv = table.get(kwc, (c15 + 1000.0 * (kwc - 15), 25.0 + kwc - 15, 0.4))
            return {'sans_panneau': False, 'kwc': kwc, 'composition': {'lignes': []},
                    'onduleurs': {'combinaison': [{'produit': 1, 'kw_ac': 10.0, 'quantite': 1}]},
                    'bilan': {'taux_couverture': couv, 'horaire': []}, 'alertes_bilan': [],
                    'economie': eco, 'cout': cout, 'puissance_ac': 10.0,
                    'prix_manquants': [], 'postes_fixes_sans_prix': []}
        with mock.patch.object(T, '_evaluer', evaluer):
            r = dimensionner_ci(
                charge_jours_types=[{'nb_jours': 365, 'charge_kwh': [1.0] * 24}],
                production_jours_types=[{'nb_jours': 365}], tension='bt',
                combiner=None, composer=None, valoriser=None)
        self.assertEqual(r['taille']['retenue_kwc'], 10)
        alerte = next(a for a in r['alertes'] if a['code'] == 'depart_hors_horizon')
        self.assertIn('%.1f' % (H + 0.1), alerte['message'])
        self.assertIn('horizon de %d ans' % H, alerte['message'])
        self.assertNotIn('%.1f' % (H - 0.1), alerte['message'])


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
    """Fondateur 26/10 et 30/10/2026 — l'option « avec batterie » C&I :
    hybrides BT à la place des string, banque homogène montée module par
    module par la règle marginale (chaque module avec les panneaux qu'il tire
    pour se remplir, QJR612), puis les panneaux par la même règle."""

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
            simuler=self.simuler, hybrides=hybrides, taux_tva_pct=20,
            cout_depart=self.sans['cout'], economie_depart=self.sans['economie'])
        params.update(kw)
        return dimensionner_option_avec(**params)

    def test_b2_option_imposee_evaluee_dans_sa_pose(self):
        # B2 (arbitrage coordinatrice) — l'option « avec » des LIGNES
        # (rafraîchisseur) prend la production de la pose qui LA loge :
        # 30,53 kWc au-delà de 21,3 kWc → série rasante, inclinaison 10 ;
        # 20,59 kWc → 30°, production de l'option « sans », rien d'ajouté.
        from apps.ventes.domain.etude_ci_batterie import option_avec_de_l_etude
        hybrides = _hybrides_bt()
        moindre = [dict(jt, production_kwh_kwc=[v * 0.9 for v in jt['production_kwh_kwc']])
                   for jt in self.prod]
        borne = {'kwc': 35.5, 'kwc_30': 21.3, 'kwc_10': 35.5, 'surface_m2': 200, 'source': 's'}

        def imposer(kwc, nb, rasante, toit=borne):
            imposee = {'kwc': kwc, 'nb_panneaux': nb, 'banque': dict(BATTERIES[1], quantite=2),
                       'investissement': None, 'empreinte': [], 'hybrides': hybrides,
                       'onduleurs': {'combinaison': [dict(hybrides[2], quantite=2)]}}
            return option_avec_de_l_etude(
                {}, None, choix=None, lead=None, imposee=imposee, charge=self.charge,
                production=self.prod, tension='bt', revente_choisie=False,
                valoriser=_valoriser(self.charge), taux_tva_pct=20, phase='tri', ps_kva=None,
                composer=_composer, borne_toit=toit,
                production_rasante=(lambda: moindre) if rasante else None)['bloc']
        avec_serie, sans_serie = imposer(30.53, 43, True), imposer(30.53, 43, False)
        self.assertEqual(avec_serie['inclinaison_retenue_deg'], 10.0)
        self.assertLess(avec_serie['bilan']['production_kwh'], sans_serie['bilan']['production_kwh'])
        bas = imposer(20.59, 29, True)
        self.assertEqual(bas['inclinaison_retenue_deg'], 30.0)
        self.assertEqual(bas['bilan']['production_kwh'],
                         imposer(20.59, 29, False)['bilan']['production_kwh'])
        # Clé ADDITIVE : absente sans les deux contenances (pente déclarée, autre pose).
        self.assertNotIn('inclinaison_retenue_deg',
                         imposer(30.53, 43, True, toit={'kwc': 21.3, 'source': 's'}))

    def test_p2_production_de_par_champ(self):
        # R1 (P2) — chaque champ « avec » est évalué avec la production de la
        # pose qui le loge : ``production_de(kwc)`` est appelée au kWc du champ.
        vus = []

        def production_de(kwc):
            vus.append(kwc)
            return self.prod
        e = self._avec(production_de=production_de)['evaluation']
        self.assertEqual(e['kwc'], self._avec()['evaluation']['kwc'])
        self.assertTrue(vus and all(isinstance(k, float) for k in vus))
        self.assertIn(e['kwc'], vus)

    def test_boulangerie_hybrides_bt_banque_homogene_toujours_pleine(self):
        from apps.ventes.moteur_ci.batterie import besoin_nocturne_kwh
        e = self._avec()['evaluation']
        self.assertIsNotNone(e)
        self.assertTrue({x['produit'] for x in e['onduleurs']['combinaison']} <= {900, 901, 902})
        bat = e['batterie']
        self.assertIn(bat['produit'], (950, 951, 952))
        # CMP8 : le besoin dépend de la fenêtre de surplus, donc du champ de
        # DÉPART arrondi aux panneaux (plus seulement des heures sans production).
        import math
        from apps.ventes.moteur_ci.autoconso import bilan_horaire
        n_bas = math.ceil(self.sans['kwc'] * 1000.0 / PANNEAU_WC - 1e-9)
        bilan_depart = bilan_horaire(self.charge, self.prod, n_bas * PANNEAU_WC / 1000.0,
                                     tension='bt', revente_choisie=False)[0]
        besoin = besoin_nocturne_kwh(self.charge, bilan_depart)
        self.assertAlmostEqual(bat['besoin_nocturne_kwh'], round(besoin, 2), places=2)
        # Fondateur 30/10/2026 : la banque ne couvre plus TOUTE la nuit — elle
        # s'arrête au module dont le pas (module + panneaux tirés) sort de l'horizon.
        self.assertGreaterEqual(bat['quantite'], 1)
        self.assertLess(bat['capacite_utile_kwh'] * bat['rendement'], besoin)
        self.assertTrue(bat['se_remplit_tous_les_jours'])
        # Le pas marginal de l'option retenue depuis « sans » tient dans l'horizon.
        from apps.ventes.dimensionnement import ratio_pas_marginal
        ratio = ratio_pas_marginal(self.sans['cout'], self.sans['economie'], e['cout'], e['economie'])
        self.assertLessEqual(ratio, HORIZON_MARGINAL_CI + 1e-9)
        self.assertGreaterEqual(e['kwc'], self.sans['kwc'])
        self.assertGreater(e['bilan']['batterie']['restitue_kwh_an'], 0)
        self.assertGreater(e['bilan']['autoconso_kwh'], self.sans['bilan']['autoconso_kwh'])
        # Batterie au prix de VENTE dans le coût de l'option, jamais un achat.
        ligne = [li for li in e['composition']['lignes'] if li['role'] == 'batterie_ci'][0]
        self.assertEqual(ligne['quantite'], bat['quantite'])
        self.assertTrue(ligne['prix_connu'])

    def test_modele_de_banque_le_moins_cher_par_kwh_utile(self):
        from apps.ventes.moteur_ci.batterie import choisir_modele_banque
        attendu = min((b for b in BATTERIES), key=lambda b: float(b['prix']) / b['kwh_utile'])
        modele = choisir_modele_banque(BATTERIES)
        self.assertEqual((modele['produit'], modele['quantite']), (attendu['produit'], 1))
        # Même prix au kWh : le prix unitaire le plus bas ; sans prix ni capacité : écarté.
        egaux = [dict(BATTERIES[0], produit=1, kwh_utile=5.0, prix=Decimal('10000')),
                 dict(BATTERIES[0], produit=2, kwh_utile=10.0, prix=Decimal('20000'))]
        self.assertEqual(choisir_modele_banque(egaux)['produit'], 1)
        self.assertIsNone(choisir_modele_banque([dict(b, prix=None) for b in BATTERIES]))
        self.assertIsNone(choisir_modele_banque([dict(b, kwh_utile=0) for b in BATTERIES]))

    def test_banque_regle_marginale_panneaux_tires_comptes(self):
        # Fondateur 30/10/2026 — 1 kWc par panneau, surplus du mois le plus bas
        # = 0,5 kWh par panneau : un module de 10 kWh utiles tire 20 panneaux.
        # Module 40 000 HT ; gains +10 000/an (1er), +10 000/an (2e),
        # +3 000/an (3e). « Sans » : 20 panneaux, 20 000 HT, 30 000 MAD/an.
        # Tout est exprimé en H = HORIZON_MARGINAL_CI (changer la valeur ne
        # change pas ce test).
        from apps.ventes.moteur_ci.batterie import _monter_banque
        self.assertLess(H, 20)
        modele = {'produit': 7, 'nom': 'Module 10 kWh', 'kwh_utile': 10.0, 'rendement': 1.0,
                  'prix': Decimal('40000'), 'max_modules': None}
        gains = {1: 10000.0, 2: 20000.0, 3: 23000.0}

        def bilan_de(n):
            return {'horaire': [{'mois': 1, 'type_jour': 'semaine', 'nb_jours': 30,
                                 'surplus_kwh': [0.5 * n] + [0.0] * 23,
                                 'autoconso_kwh': [0.0] * 24}]}

        def combiner(_kwc):
            return {'combinaison': [{'produit': 9, 'quantite': 1, 'kw_ac': 100.0}]}

        def monter(prix_panneau, n_haut=100, prix_module=40000.0):
            vus = []

            def evaluer(n, banque):
                q = int(banque['quantite'])
                vus.append((q, n))
                return {'n': n, 'cout': prix_panneau * n + prix_module * q,
                        'economie': 30000.0 + gains.get(q, 23000.0)}
            r = _monter_banque(modele, n_bas=20, n_haut=n_haut, pmax_wc=1000.0,
                               bilan_de=bilan_de, combiner=combiner, ps_kva=None,
                               evaluer=evaluer, cout_depart=prix_panneau * 20,
                               economie_depart=30000.0)
            return r, vus
        # Panneaux à 1 000 HT : module 1 = 40 000 / 10 000 = 4 ans (gardé) ;
        # module 2 = (40 000 + 20 panneaux tirés) / 10 000 = 6 ans (gardé) ;
        # module 3 = 60 000 / 3 000 = 20 ans (refusé), module 4 sans gain
        # (fin du balayage) ⇒ 2 modules, 40 panneaux.
        (e, banque, reduite), vus = monter(1000.0)
        self.assertEqual((banque['quantite'], e['n'], reduite), (2, 40, False))
        self.assertEqual(vus, [(1, 20), (2, 40), (3, 60), (4, 80)])
        # Panneaux plus chers : le module 2 seul vaut 4 ans mais, AVEC ses 20
        # panneaux tirés, (40 000 + 20 × prix) / 10 000 = H + 1 an ⇒ refusé : 1 module.
        prix_ko = (10000.0 * (H + 1) - 40000.0) / 20
        (e, banque, reduite), _vus = monter(prix_ko)
        self.assertEqual((banque['quantite'], e['n'], reduite), (1, 20, False))
        # Toit à 30 panneaux : le 2e module ne se remplit pas ⇒ banque réduite à 1, nommée.
        (e, banque, reduite), _vus = monter(1000.0, n_haut=30)
        self.assertEqual((banque['quantite'], e['n'], reduite), (1, 20, True))
        # Module à 10 000 × (H + 3) : aucun module (ni groupe) ne tient dans
        # l'horizon ⇒ aucune option « avec », motif nommé avec le retour du premier.
        r, _vus = monter(1000.0, prix_module=10000.0 * (H + 3))
        self.assertIsNone(r['evaluation'])
        self.assertIn('%d ans' % H, r['motif'])
        self.assertIn('%.1f ans' % (H + 3), r['motif'])
        # Regard (fondateur 26/10) : le 1er module porte un coût FIXE de
        # 10 000 × (H + 3) (passage aux hybrides) — H + 3 ans seul ; 0 → 2 =
        # (fixe + 80 000 + 20 panneaux) / 20 000 = H/2 + 6,5 (non) ; 0 → 3 à
        # +3 000/an = (fixe + 160 000) / 23 000 (non) ⇒ rien ; avec un 3e module
        # dont le gain porte 0 → 3 à H − 0,5 an ⇒ 3 modules.
        fixe = 10000.0 * (H + 3)
        gains_fixe = {1: 10000.0, 2: 20000.0, 3: round((fixe + 160000.0) / (H - 0.5) + 1)}

        def monter_fixe(gains_q):
            def evaluer(n, banque):
                q = int(banque['quantite'])
                return {'n': n, 'cout': 1000.0 * n + 40000.0 * q + fixe,
                        'economie': 30000.0 + gains_q.get(q, gains_q[max(gains_q)])}
            return _monter_banque(modele, n_bas=20, n_haut=100, pmax_wc=1000.0,
                                  bilan_de=bilan_de, combiner=combiner, ps_kva=None,
                                  evaluer=evaluer, cout_depart=20000.0, economie_depart=30000.0)
        self.assertIsNone(monter_fixe(gains)['evaluation'])
        e, banque, reduite = monter_fixe(gains_fixe)
        self.assertEqual((banque['quantite'], e['n'], reduite), (3, 60, False))

    def test_d_ci_batterie_non_rentable_meilleur_groupe_montre(self):
        # D-CI-BATTERIE-NON-RENTABLE (fondateur 30/10/2026, niveau 5) : aucun
        # groupe ne tient dans l'horizon ⇒ le groupe au MEILLEUR retour du
        # supplément (remplacement de la batterie compris) parmi ceux que la
        # montée évalue, au lieu d'aucune option ; sans ``remplacement``
        # (niveaux ≤ 4) : l'ancien refus, octet pour octet.
        from apps.ventes.moteur_ci.batterie import _meilleur_groupe, _monter_banque
        self.assertEqual(H, 10)
        modele = {'produit': 7, 'nom': 'Module 10 kWh', 'kwh_utile': 10.0, 'rendement': 1.0,
                  'prix': Decimal('40000'), 'max_modules': None}

        def bilan_de(n):
            return {'horaire': [{'mois': 1, 'type_jour': 'semaine', 'nb_jours': 30,
                                 'surplus_kwh': [0.5 * n] + [0.0] * 23,
                                 'autoconso_kwh': [0.0] * 24}]}

        def combiner(_kwc):
            return {'combinaison': [{'produit': 9, 'quantite': 1, 'kw_ac': 100.0}]}
        # Coût FIXE 130 000 (passage aux hybrides), module 40 000, panneau
        # 1 000 ; gains +10 000 / +20 000 / +23 000 / +23 000. Supplément sur
        # « sans » (20 panneaux, 20 000, 30 000/an) : 1 module 17 ans,
        # 2 modules 11,5 ans, 3 modules 12,6 ans, 4 modules 15,2 ans — aucun ≤ 10.
        gains = {1: 10000.0, 2: 20000.0, 3: 23000.0}

        def monter(remplacement):
            def evaluer(n, banque):
                q = int(banque['quantite'])
                return {'n': n, 'cout': 1000.0 * n + 40000.0 * q + 130000.0,
                        'economie': 30000.0 + gains.get(q, 23000.0)}
            return _monter_banque(modele, n_bas=20, n_haut=100, pmax_wc=1000.0,
                                  bilan_de=bilan_de, combiner=combiner, ps_kva=None,
                                  evaluer=evaluer, cout_depart=20000.0,
                                  economie_depart=30000.0, remplacement=remplacement)
        ancien = monter(None)
        self.assertIsNone(ancien['evaluation'])
        self.assertIn('%d ans' % H, ancien['motif'])
        e, banque, reduite = monter(lambda e, b: (0.0, None))
        self.assertEqual((banque['quantite'], e['n'], reduite), (2, 40, False))
        # Remplacement des modules en année 2 (40 000 × q) : 1 module 21 ans,
        # 2 modules 15,5 ans, 3 modules 17,8 ans ⇒ toujours 2 modules.
        e, banque, _r = monter(lambda e, b: (40000.0 * int(b['quantite']), 2))
        self.assertEqual(banque['quantite'], 2)
        # Égalité de retour ⇒ le moins de modules.
        e1, e2 = {'cout': 100.0, 'economie': 10.0}, {'cout': 200.0, 'economie': 20.0}
        banques = {id(e1): {'quantite': 1}, id(e2): {'quantite': 2}}
        depart = {'cout': 0.0, 'economie': 0.0}
        self.assertIs(_meilleur_groupe(depart, [e2, e1], banques, lambda e, b: (0.0, None)), e1)
        # Aucun gain ⇒ aucun groupe.
        self.assertIsNone(_meilleur_groupe({'cout': 0.0, 'economie': 50.0}, [e1, e2], banques,
                                           lambda e, b: (0.0, None)))

    def test_d_ci_batterie_non_rentable_boulangerie_niveau_4_vs_5(self):
        # Boulangerie, modules hors de prix : niveau ≤ 4 (aucun ``remplacement``)
        # ⇒ aucune option « avec », motif nommé ; niveau 5 ⇒ option composée
        # au meilleur groupe, son supplément hors de l'horizon.
        from apps.ventes.moteur_ci.batterie import cout_batterie_ht, retour_marginal_batterie
        chere = [dict(b, prix=Decimal('900000'),
                      element=dict(b['element'], prix_vente_ht=Decimal('900000')))
                 for b in BATTERIES]
        ancien = self._avec(batteries=chere)
        self.assertIsNone(ancien['evaluation'])
        self.assertIn('%d ans' % H, ancien['motif'])
        r = self._avec(batteries=chere, remplacement=lambda e, b: (
            cout_batterie_ht(e.get('composition'), 20), 11))
        e = r['evaluation']
        self.assertIsNotNone(e)
        self.assertGreaterEqual(e['batterie']['quantite'], 1)
        self.assertGreater(retour_marginal_batterie(self.sans['cout'], self.sans['economie'],
                                                    e['cout'], e['economie']), H)

    def test_retour_marginal_batterie_remplacement_compte_apres_son_annee(self):
        from apps.ventes.moteur_ci.batterie import retour_marginal_batterie
        # Supplément 100 000, gain 10 000/an : 10 ans ; remplacement 50 000 en
        # année 11 ⇒ remboursé avant (10 ≤ 11 − 1) : non compté.
        self.assertEqual(retour_marginal_batterie(0, 0, 100000, 10000, 50000, 11), 10.0)
        # Supplément 136 000 : 13,6 ans > 11 − 1 ⇒ (136 000 + 50 000) / 10 000.
        self.assertEqual(retour_marginal_batterie(0, 0, 136000, 10000, 50000, 11), 18.6)
        self.assertEqual(retour_marginal_batterie(0, 0, 136000, 10000, 50000, None), 13.6)
        self.assertIsNone(retour_marginal_batterie(0, 10000, 100000, 10000))

    def test_aucune_batterie_tarifee_motif_et_prix_nommes(self):
        sans_prix = [dict(b, prix=None) for b in BATTERIES]
        r = self._avec(batteries=sans_prix)
        self.assertIsNone(r['evaluation'])
        self.assertIn('Batterie Dyness 10 kWh', r['prix_a_renseigner'])

    def test_toit_borne_banque_reduite_nommee(self):
        # Modules Dyness 5 kWh à 1 MAD : chaque module passe la règle marginale ;
        # seul le toit (champ « sans » gardé) arrête la banque — réduite, nommée.
        gratuite = dict(BATTERIES[0], prix=Decimal('1'),
                        element=dict(BATTERIES[0]['element'], prix_vente_ht=Decimal('1')))
        r = self._avec(kwc_max=self.sans['kwc'], batteries=[gratuite])
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

    def test_au_plus_10_hybrides_en_parallele_champ_borne_et_alerte(self):
        # CMP3 : départ 400 kWc ⇒ plus de 10 hybrides ; le champ « avec » est le
        # plus grand champ porté par 10 appareils (Deye « Max. 10 pcs parallel »).
        from apps.ventes.moteur_ci.batterie import MAX_HYBRIDES_PARALLELE
        # Aucune option « sans » à 400 kWc dans la fixture : sans point n = 0,
        # le premier module est admis d'office (la borne CMP3 est ce qu'on teste).
        r = self._avec(kwc_depart=400.0, cout_depart=None, economie_depart=None,
                       combiner=partial(combiner_onduleurs, candidats=_hybrides_bt(),
                                        phase='tri', max_appareils=MAX_HYBRIDES_PARALLELE))
        e = r['evaluation']
        self.assertIsNotNone(e)
        self.assertLessEqual(sum(x['quantite'] for x in e['onduleurs']['combinaison']), 10)
        self.assertLess(e['kwc'], 400.0)
        self.assertIn('HYBRIDES_PARALLELE_MAX', [a['code'] for a in r['alertes']])
        # Le champ a RETRECI : jamais masque par un « ajoutes » a 0.
        self.assertEqual(e['batterie']['panneaux_ajoutes'], 0)
        self.assertGreater(e['batterie']['panneaux_retires'], 0)

    def test_cmp7_decharge_bornee_par_les_ports_hybrides(self):
        # 2 SUN-15K (port 14,34 kW, AC 15 kW), charge de nuit de 40 kW : la
        # restitution de chaque heure ≤ 28,68 kWh ; borne non publiée ⇒ inchangé.
        from apps.ventes.moteur_ci.batterie import (
            _batterie_sur_jour, puissance_decharge_kw)
        onduleurs = {'combinaison': [{'produit': 901, 'quantite': 2}]}
        hyb = [dict(h, bat_max_decharge_kw=14.34) if h['produit'] == 901 else h
               for h in _hybrides_bt()]
        banque = dict(BATTERIES[2], quantite=4)
        self.assertAlmostEqual(puissance_decharge_kw(banque, onduleurs, hyb), 28.68, places=6)
        # Port plus grand que l'AC : plafonné par Σ kW AC (2 × 15).
        hyb_large = [dict(h, bat_max_decharge_kw=20.0) if h['produit'] == 901 else h
                     for h in _hybrides_bt()]
        self.assertEqual(puissance_decharge_kw(banque, onduleurs, hyb_large), 30.0)
        # Pack seul publié : Σ packs ; rien de publié : None.
        self.assertEqual(puissance_decharge_kw(dict(banque, max_decharge_kw=5.0), {}, []), 20.0)
        self.assertIsNone(puissance_decharge_kw(banque, onduleurs, _hybrides_bt()))
        bloc = {'autoconso_kwh': [0.0] * 24, 'surplus_kwh': [30.0] * 6 + [0.0] * 18}
        nuit = [0.0] * 6 + [40.0] * 18
        aucune = _batterie_sur_jour(nuit, bloc, 60.0, 1.0, None, self.simuler)
        self.assertAlmostEqual(aucune[2], 60.0)        # la banque pleine se vide
        large = _batterie_sur_jour(nuit, bloc, 60.0, 1.0, None, self.simuler, 28.68)
        self.assertAlmostEqual(large[2], 60.0)         # 60 kWh tiennent en 3 h
        serree = _batterie_sur_jour(nuit, bloc, 60.0, 1.0, None, self.simuler, 2.0)
        self.assertAlmostEqual(serree[2], 36.0)        # 18 h × 2 kWh/h, le reste au réseau
        self.assertLessEqual(max(serree[0][6:]), 2.0 + 1e-9)
        # Borne None ⇒ strictement identique au comportement d'avant.
        self.assertEqual(aucune, _batterie_sur_jour(nuit, bloc, 60.0, 1.0, None, self.simuler, None))

    def test_cmp8_besoin_hors_fenetre_solaire(self):
        # Surplus de 10 h à 16 h ; charge 20 kWh/h à 17-18 h pour 5 kWh/h de
        # production : ces 2 × 15 = 30 kWh de déficit du soir comptent.
        from apps.ventes.moteur_ci.batterie import besoin_nocturne_kwh
        charge, auto, surplus = [0.0] * 24, [0.0] * 24, [0.0] * 24
        for h in range(10, 17):
            auto[h], surplus[h] = 5.0, 10.0
        for h in (17, 18):
            charge[h], auto[h] = 20.0, 5.0
        charge[3] = 4.0                  # nuit : 4 kWh, production nulle
        bloc = {'mois': 6, 'type_jour': 'semaine', 'nb_jours': 20,
                'autoconso_kwh': auto, 'surplus_kwh': surplus}
        jt = [{'mois': 6, 'type_jour': 'semaine', 'charge_kwh': charge}]
        self.assertAlmostEqual(besoin_nocturne_kwh(jt, {'horaire': [bloc]}), 34.0)
        # Jour sans surplus ⇒ 0 ; pondération par nb_jours conservée.
        sans = dict(bloc, surplus_kwh=[0.0] * 24)
        autre = dict(sans, type_jour='dimanche')
        jt2 = jt + [{'mois': 6, 'type_jour': 'dimanche', 'charge_kwh': charge}]
        self.assertAlmostEqual(besoin_nocturne_kwh(jt2, {'horaire': [bloc, autre]}), 17.0)
        self.assertEqual(besoin_nocturne_kwh(jt, {'horaire': [sans]}), 0.0)

    def test_cmp7_option_servie_borne_publiee_baisse_economie(self):
        hyb_libres = _hybrides_bt()
        r0 = self._avec(hybrides=hyb_libres)['evaluation']
        self.assertIsNone(r0['batterie']['puissance_decharge_kw'])
        # Port de décharge de 0,5 kW : la banque ne rend presque rien, aucun
        # module ne tient dans l'horizon — sans point n = 0, le premier est admis
        # d'office, ce qui est ce que la borne CMP7 doit montrer.
        serres = [dict(h, bat_max_decharge_kw=0.5) for h in hyb_libres]
        r1 = self._avec(hybrides=serres, cout_depart=None, economie_depart=None,
                        combiner=partial(combiner_onduleurs, candidats=serres,
                                         phase='tri'))['evaluation']
        self.assertEqual(r1['batterie']['puissance_decharge_kw'], 0.5 * sum(
            x['quantite'] for x in r1['onduleurs']['combinaison']))
        self.assertLess(r1['bilan']['batterie']['restitue_kwh_an'],
                        r0['bilan']['batterie']['restitue_kwh_an'])

    def test_regle_marginale_au_dela_du_remplissage(self):
        from apps.ventes.moteur_ci.batterie import monter_regle_marginale
        # n → kWc = n × 710 Wc ; coût 1 000 MAD/kWc ; économie 300 MAD/kWc
        # (3,3 ans) jusqu'à 40 kWc, puis 50 MAD/kWc (20 ans par palier) : arrêt à 40.

        def evaluer(n):
            kwc = n * PANNEAU_WC / 1000.0
            eco = 300 * min(kwc, 40) + 50 * max(0.0, kwc - 40)
            return {'kwc': kwc, 'cout': 1000 * kwc, 'economie': eco}
        retenu = monter_regle_marginale(29, 200, PANNEAU_WC, evaluer)
        self.assertLessEqual(abs(retenu['kwc'] - 40), PANNEAU_WC / 1000.0)
        self.assertIsNone(monter_regle_marginale(29, 200, PANNEAU_WC, lambda n: None))
        # Un palier à H + 1 an : refusé à l'horizon C&I, gardé à un horizon explicite de H + 2.

        def hors_horizon(n):
            kwc = n * PANNEAU_WC / 1000.0
            return {'kwc': kwc, 'cout': 1000 * kwc, 'economie': 1000 / (H + 1) * kwc}
        self.assertEqual(monter_regle_marginale(29, 60, PANNEAU_WC, hors_horizon)['kwc'],
                         29 * PANNEAU_WC / 1000.0)
        self.assertGreater(monter_regle_marginale(29, 60, PANNEAU_WC, hors_horizon,
                                                  horizon=H + 2)['kwc'],
                           29 * PANNEAU_WC / 1000.0)


class PoseRasanteR1Tests(unittest.TestCase):
    """R1 — décision fondateur du 28/10/2026 (toit plat SANS pente déclarée) :
    la taille est choisie par l'économie sans être bornée par la pose à 30° ;
    un palier qui ne tient pas à 30° est évalué (production, panneaux entiers)
    en pose rasante 10° ; la borne toit ne joue que si même la rasante ne
    suffit pas, et le devis le dit. Contenances du VRAI service de calepinage
    (``core.calepinage.contenance_declaree``, module 2 384 × 1 303 mm, 200 m²
    à Casablanca) : 30 panneaux = 21,3 kWc à 30°, 50 panneaux = 35,5 kWc en
    pose rasante jointive — jamais un ratio en dur."""

    KWC_30, KWC_10, SURFACE = 21.3, 35.5, 200

    @classmethod
    def setUpClass(cls):
        cls.prod, _ = _production()
        cls.huawei = _catalogue_huawei()

    def _bornes(self, kwc_30=KWC_30, kwc_10=KWC_10, surface=SURFACE):
        return {'toit': {
            'kwc': max(kwc_30, kwc_10), 'kwc_30': kwc_30, 'kwc_10': kwc_10,
            'surface_m2': surface,
            'source': 'surface utile déclarée (%g m²), pose estimée « toit_plat_leste »' % surface,
            'source_30': 'tables à 30°', 'source_10': 'pose rasante 10°'}}

    def _taille(self, charge, **kw):
        appels = []

        def production_rasante():
            appels.append(1)
            return self.prod
        r = dimensionner_ci(
            charge_jours_types=charge, production_jours_types=self.prod, tension='bt',
            combiner=partial(combiner_onduleurs, candidats=self.huawei, phase='tri'),
            composer=_composer, valoriser=_valoriser(charge), taux_tva_pct=20,
            pmax_wc=PANNEAU_WC, production_rasante=production_rasante, **kw)
        r['appels_rasante'] = len(appels)
        return r

    @staticmethod
    def _hyp(r, cle):
        return next((h for h in r['hypotheses'] if h['cle'] == cle), None)

    def test_a_boulangerie_200_m2_logee_en_pose_rasante_jamais_20(self):
        # Lead 1637 : 120 MWh/an, 6 h-22 h, BT patenté, 200 m² déclarés, toit
        # plat lesté sans pente. Avant R1 : 20,02 kWc par la seule borne 30°.
        charge, _prov, _al = courbe_declaree(
            {'plages': {'ouvre': [[6, 22]]}, 'jours_ouverts': [True] * 7},
            [10000] * 12, annee_reference=2025, archetype='boulangerie')
        r = self._taille(charge, bornes=self._bornes())
        t = r['taille']
        self.assertGreater(t['retenue_kwc'], self.KWC_30)
        self.assertEqual(r['inclinaison_retenue_deg'], 10.0)
        self.assertEqual(self._hyp(r, 'inclinaison_retenue_deg')['valeur'], 10.0)
        self.assertGreater(r['appels_rasante'], 0)
        # Le service loge 50 panneaux (35,5 kWc) en rasante ; l'économie en
        # voudrait plus (sans toit, la montée continue) : la borne toit joue.
        self.assertEqual((t['retenue_kwc'], t['nb_panneaux'], t['raison_arret']),
                         (35.5, 50, 'toit'))
        self.assertGreater(self._taille(charge)['taille']['retenue_kwc'], t['retenue_kwc'])
        # P3 — servi dans ``taille`` (ce que le générateur lit), pas seulement en hypothèse.
        self.assertEqual(t['inclinaison_retenue_deg'], 10.0)
        self.assertEqual(t['taille_limitee_toit'],
                         'taille limitée par le toit : 200 m² déclarés → 35.5 kWc en pose rasante')

    def test_b_taille_qui_tient_a_30_garde_30_et_la_meme_taille(self):
        charge = _charge('bureau', 6000)
        avant = self._taille(charge)
        r = self._taille(charge, bornes=self._bornes(kwc_30=400, kwc_10=500, surface=3000))
        self.assertEqual(r['taille']['retenue_kwc'], avant['taille']['retenue_kwc'])
        self.assertEqual(r['taille']['raison_arret'], 'horizon_marginal')
        self.assertEqual(r['inclinaison_retenue_deg'], 30.0)
        self.assertEqual(self._hyp(r, 'inclinaison_retenue_deg')['valeur'], 30.0)
        self.assertIsNone(self._hyp(r, 'taille_limitee_toit'))
        self.assertEqual((r['taille']['inclinaison_retenue_deg'], r['taille']['taille_limitee_toit']),
                         (30.0, None))
        self.assertEqual(r['appels_rasante'], 0)             # série 10° jamais lue
        self.assertIsNone(avant['inclinaison_retenue_deg'])  # sans toit : rien à dire
        self.assertEqual((avant['taille']['inclinaison_retenue_deg'],
                          avant['taille']['taille_limitee_toit']), (None, None))

    def test_c_meme_la_rasante_ne_suffit_pas_raison_toit_texte_client(self):
        r = self._taille(_charge('hotel', 20000), bornes=self._bornes())
        t = r['taille']
        self.assertEqual((t['retenue_kwc'], t['nb_panneaux'], t['raison_arret']),
                         (35.5, 50, 'toit'))
        self.assertEqual(t['paliers'][-1]['borne'], 'toit')
        self.assertEqual(r['inclinaison_retenue_deg'], 10.0)
        self.assertEqual(self._hyp(r, 'taille_limitee_toit')['source'],
                         'taille limitée par le toit : 200 m² déclarés → 35.5 kWc en pose rasante')
        self.assertEqual((t['bornes']['toit']['kwc_30'], t['bornes']['toit']['kwc_10']),
                         (21.3, 35.5))
        # Les paliers ≤ 21,3 kWc restent évalués à 30° ; la série rasante n'est
        # lue qu'aux paliers au-delà.
        au_dela = [p for p in t['paliers'] if p['kwc'] > self.KWC_30]
        self.assertEqual(r['appels_rasante'], len(au_dela))

    def test_d_pente_declaree_ou_toit_sans_rasante_aucun_basculement(self):
        # L'orchestrateur ne sert kwc_30/kwc_10 que pour un toit plat sans pente
        # déclarée : avec la seule contenance, la borne joue comme avant.
        r = self._taille(_charge('hotel', 20000),
                         bornes={'toit': {'kwc': 21.3, 'source': 'surface utile déclarée (200 m²)'}})
        t = r['taille']
        self.assertEqual(t['raison_arret'], 'toit')
        self.assertLessEqual(t['retenue_kwc'], 21.3)
        self.assertIsNone(r['inclinaison_retenue_deg'])
        self.assertIsNone(self._hyp(r, 'inclinaison_retenue_deg'))
        self.assertIsNone(self._hyp(r, 'taille_limitee_toit'))
        self.assertEqual((t['inclinaison_retenue_deg'], t['taille_limitee_toit']), (None, None))
        self.assertEqual(r['appels_rasante'], 0)

    def test_taille_explicite_au_dela_de_30_logee_en_rasante(self):
        charge = _charge('hotel', 20000)
        r = self._taille(charge, bornes=self._bornes(), taille_explicite_kwc=30)
        self.assertEqual(r['taille']['raison_arret'], 'taille_explicite')
        self.assertEqual(r['inclinaison_retenue_deg'], 10.0)
        self.assertEqual(r['taille']['inclinaison_retenue_deg'], 10.0)
        self.assertNotIn('taille_au_dela_du_toit', [a['code'] for a in r['alertes']])
        self.assertIsNone(r['taille']['taille_limitee_toit'])    # 30 < 35,5 − un panneau
        r2 = self._taille(charge, bornes=self._bornes(), taille_explicite_kwc=40)
        alerte = next(a for a in r2['alertes'] if a['code'] == 'taille_au_dela_du_toit')
        self.assertIn('35.5', alerte['message'])           # la borne effective, la rasante
        self.assertIsNone(r2['taille']['taille_limitee_toit'])   # au-delà : pas « limitée »

    def test_b1_taille_explicite_jamais_limitee_par_le_toit(self):
        # B1 (arbitrage coordinatrice 28/10/2026) — une taille EXPLICITE
        # (saisie, ou kWc des lignes au rafraîchissement) n'imprime JAMAIS
        # « limitée par le toit » : l'économie n'a pas été balayée. Même posée
        # pile à la contenance rasante (50 panneaux = 35,5 kWc). Le verdict
        # calculé à la création est relu par l'orchestrateur (etude_ci), pas ici.
        for kwc in (35.5, 34.79, 30):
            t = self._taille(_charge('hotel', 20000), bornes=self._bornes(),
                             taille_explicite_kwc=kwc)['taille']
            self.assertEqual(t['raison_arret'], 'taille_explicite', kwc)
            self.assertEqual(t['inclinaison_retenue_deg'], 10.0, kwc)
            self.assertIsNone(t['taille_limitee_toit'], kwc)

    def test_production_rasante_differente_pese_sur_l_economie(self):
        # La série 10° (≈ −6 % à Casablanca) ne sert qu'aux paliers logés en
        # rasante : mêmes paliers ≤ 21,3 kWc, économie moindre au-delà.
        charge = _charge('hotel', 20000)
        meme = self._taille(charge, bornes=self._bornes())
        moindre = [dict(jt, production_kwh_kwc=[v * 0.9 for v in jt['production_kwh_kwc']])
                   for jt in self.prod]
        r = dimensionner_ci(
            charge_jours_types=charge, production_jours_types=self.prod, tension='bt',
            combiner=partial(combiner_onduleurs, candidats=self.huawei, phase='tri'),
            composer=_composer, valoriser=_valoriser(charge), taux_tva_pct=20,
            pmax_wc=PANNEAU_WC, production_rasante=lambda: moindre, bornes=self._bornes())
        self.assertEqual(r['taille']['retenue_kwc'], meme['taille']['retenue_kwc'])
        self.assertLess(r['evaluation']['economie'], meme['evaluation']['economie'])
        bas = [p['economie_annuelle'] for p in r['taille']['paliers'] if p['kwc'] <= self.KWC_30]
        self.assertEqual(bas, [p['economie_annuelle'] for p in meme['taille']['paliers']
                               if p['kwc'] <= self.KWC_30])


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
