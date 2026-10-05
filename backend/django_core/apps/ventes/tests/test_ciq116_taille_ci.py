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
from apps.ventes.moteur_ci.taille import dimensionner_ci
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
        r = self._taille('bureau', 6000)
        self.assertIsNotNone(r['taille']['retenue_kwc'])
        self.assertIn('postes_fixes_sans_prix', [a['code'] for a in r['alertes']])

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
