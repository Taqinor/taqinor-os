"""CIQ205 — ``economie_ci`` (2/6) : base HT si la TVA est récupérable, TTC
sinon, les deux bases quand c'est inconnu (D-CIQ-3).

SimpleTestCase : aucune base.
"""
from django.test import SimpleTestCase

from apps.ventes import economie_ci as eco
from apps.ventes import tarif_ci as tc


def _bureau_360k():
    """Bureau 360 000 TTC dont 50 % du HT en panneaux (TVA 10 %), le reste à
    20 % : HT × (0,5 × 1,10 + 0,5 × 1,20) = HT × 1,15 = 360 000."""
    ht = 360000 / 1.15
    lignes = [
        {'taux_tva': 10, 'totaux': {'ht': ht / 2, 'ttc': ht / 2 * 1.10}},
        {'taux_tva': 20, 'totaux': {'ht': ht / 2, 'ttc': ht / 2 * 1.20}},
    ]
    return {'ht': round(sum(li['totaux']['ht'] for li in lignes), 2),
            'ttc': round(sum(li['totaux']['ttc'] for li in lignes), 2)}


def _economie_repli_mt():
    tarif = tc.tarif_applicable(None, tension='mt')
    horaire = [{'mois': m, 'type_jour': 'ouvre', 'nb_jours': 30,
                'autoconso_kwh': [20.0 if 8 <= h < 17 else 0.0
                                  for h in range(24)],
                'surplus_kwh': [0.0] * 24} for m in range(1, 13)]
    jours = [{'mois': m, 'type_jour': 'ouvre', 'nb_jours': 30,
              'charge_kwh': [30.0] * 24} for m in range(1, 13)]
    res = eco.valoriser({'entrees_resolues': {'tension': {'valeur': 'mt'}},
                         'profil_charge': {'jours_types': jours},
                         'bilan': {'horaire': horaire}}, tarif)
    return res['economie_annee1']


class BaseHtTest(SimpleTestCase):
    def test_bureau_360k_base_ht(self):
        economie = _economie_repli_mt()
        res = eco.base_economique('oui', investissement=_bureau_360k(),
                                  economie_annee1=economie)
        self.assertEqual(res['base'], 'ht')
        self.assertEqual(res['flux'], ['flux_ht'])
        self.assertEqual(round(res['investissement_ht_mad']), 313043)
        self.assertEqual(res['investissement_ttc_mad'], 360000.0)
        # Repli grille : HT dérivé = TTC ÷ 1,20 (TVA électricité 2026), au
        # prix HT arrondi à 4 décimales près (tarif_ci._r4).
        attendu = res['economie_annee1_ttc_mad'] / 1.20
        self.assertAlmostEqual(res['economie_annee1_ht_mad'], attendu,
                               delta=attendu * 1e-4)
        self.assertIn('« oui »', res['motif_base'])

    def test_base_amortissable_vaut_le_ht(self):
        res = eco.base_economique('oui', investissement=_bureau_360k())
        self.assertEqual(res['base_amortissable_mad'],
                         res['investissement_ht_mad'])


class BaseTtcEtDeuxTest(SimpleTestCase):
    def test_non_ttc_ttc(self):
        res = eco.base_economique('non', investissement=_bureau_360k(),
                                  economie_annee1=_economie_repli_mt())
        self.assertEqual(res['base'], 'ttc')
        self.assertEqual(res['flux'], ['flux_ttc'])
        self.assertEqual(res['base_amortissable_mad'], 360000.0)

    def test_inconnu_deux_flux_et_motif(self):
        res = eco.base_economique('inconnu', investissement=_bureau_360k())
        self.assertEqual(res['base'], 'deux')
        self.assertEqual(res['flux'], ['flux_ht', 'flux_ttc'])
        self.assertIn('statut TVA non déclaré', res['motif_base'])
        self.assertIn('les deux bases sont montrées', res['motif_base'])
        self.assertIsNone(res['base_amortissable_mad'])

    def test_valeur_hors_liste_traitee_comme_inconnue(self):
        self.assertEqual(eco.base_economique(None)['base'], 'deux')
        self.assertEqual(eco.base_economique('ne_sait_pas')['base'], 'deux')


class ResolutionTest(SimpleTestCase):
    def test_lead_d_abord(self):
        res = eco.resoudre_tva_recuperable(
            'oui', {'valeur': 'non', 'provenance': 'declare_client'})
        self.assertEqual(res['valeur'], 'oui')
        self.assertEqual(res['provenance'], 'lead')

    def test_lead_ne_sait_pas_puis_saisie(self):
        res = eco.resoudre_tva_recuperable(
            'ne_sait_pas', {'valeur': 'non', 'provenance': 'declare_client',
                            'saisi_le': '2026-09-15'})
        self.assertEqual(res['valeur'], 'non')
        self.assertEqual(res['saisi_le'], '2026-09-15')

    def test_rien_de_declare_inconnu(self):
        self.assertEqual(eco.resoudre_tva_recuperable()['valeur'], 'inconnu')

    def test_saisie_invalide_refusee_en_nommant_le_champ(self):
        with self.assertRaises(eco.SaisieEconomieCiInvalide) as ctx:
            eco.lire_saisie_tva({'valeur': 'peut-etre'})
        self.assertEqual(ctx.exception.champ,
                         'saisies_economie_ci.tva_recuperable.valeur')

    def test_enregistrer_rouvrir_enregistrer_identique(self):
        saisie = {'valeur': 'inconnu', 'provenance': 'lead',
                  'saisi_le': '2026-09-15'}
        une = eco.lire_saisie_tva(saisie)
        deux = eco.lire_saisie_tva(une)
        self.assertEqual(une, saisie)
        self.assertEqual(deux, une)
