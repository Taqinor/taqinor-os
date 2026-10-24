"""CIQ206 — ``economie_ci`` (3/6) : UN flux 25 ans par
``economie.flux_de_tresorerie``, jalons 5/10/15/20/25, TRI avec son horizon,
VAN sur le seul taux DÉCLARÉ du client, coût du kWh à côté du tarif évité.

SimpleTestCase : aucune base.
"""
from django.test import SimpleTestCase

from apps.ventes import economie_ci as eco


def _base(tva='oui', inv=400000.0, economie=80000.0):
    return eco.base_economique(
        tva, investissement={'ht': inv, 'ttc': inv * 1.2},
        economie_annee1={'total_mad': economie,
                         'total_mad_ttc': economie * 1.2})


class CasDeReferenceTest(SimpleTestCase):
    def test_cumuls_aux_cinq_jalons_recalcules_a_la_main(self):
        res = eco.flux_ci(_base(), production_annee1_kwh=100000)
        # Recalcul indépendant : économie_t = 80 000 × 0,995^(t−1).
        cumul, attendus = -400000.0, {}
        for t in range(1, 26):
            cumul += 80000.0 * 0.995 ** (t - 1)
            if t in (5, 10, 15, 20, 25):
                attendus[t] = round(cumul, 2)
        jalons = {j['annee']: j['cumul_mad'] for j in res['jalons']}
        self.assertEqual(sorted(jalons), [5, 10, 15, 20, 25])
        for annee, valeur in attendus.items():
            self.assertAlmostEqual(jalons[annee], valeur, places=1)
        self.assertEqual(res['flux_ht']['horizon_ans'], 25)
        self.assertEqual(res['indicateurs']['tri_horizon_ans'], 25)
        self.assertEqual(res['indicateurs']['retour_ans'], 6)
        self.assertIsNotNone(res['indicateurs']['tri_pct'])
        self.assertIsNone(res['flux_ttc'])

    def test_hypotheses_explicites_et_sourcees(self):
        bloc = eco.flux_ci(_base(), production_annee1_kwh=100000)['flux_ht']
        hyp = {h['cle']: h for h in bloc['hypotheses']}
        self.assertEqual(hyp['indexation_pct']['valeur'], 0.0)
        self.assertIn('tarif de vente constant',
                      hyp['indexation_pct']['source'])
        self.assertEqual(hyp['degradation_pct']['valeur'], 0.5)
        self.assertIn('NREL/JA-5200-51664', hyp['degradation_pct']['source'])


class ProductionParAnneeTest(SimpleTestCase):
    def test_production_de_chaque_annee_meme_degradation(self):
        """AMOT94 — chaque ligne du flux porte sa production : 100 000 kWh ×
        0,995^(t−1) (la dégradation servie), None en année 0 — recalcul
        indépendant, au kWh près."""
        res = eco.flux_ci(_base(), production_annee1_kwh=100000)
        lignes = {f['annee']: f['production_kwh'] for f in
                  res['flux_ht']['flux']}
        self.assertIsNone(lignes[0])
        for t in range(1, 26):
            self.assertEqual(lignes[t], round(100000 * 0.995 ** (t - 1)), t)

    def test_sans_production_servie_aucune_production(self):
        res = eco.flux_ci(_base(), production_annee1_kwh=None)
        self.assertTrue(all(f.get('production_kwh') is None
                            for f in res['flux_ht']['flux']))


class OnduleurTest(SimpleTestCase):
    def test_remplacement_annee_12_au_montant_de_sa_ligne(self):
        res = eco.flux_ci(_base(), production_annee1_kwh=100000,
                          onduleur={'ht': 30000.0, 'ttc': 36000.0,
                                    'source': 'ligne onduleur du devis'})
        flux = {f['annee']: f for f in res['flux_ht']['flux']}
        self.assertAlmostEqual(
            flux[12]['economie_mad'] - flux[12]['flux_mad'], 30000.0,
            places=1)
        self.assertAlmostEqual(
            flux[11]['economie_mad'] - flux[11]['flux_mad'], 0.0, places=1)
        self.assertEqual(res['remplacements'][0]['annee'], 12)
        self.assertEqual(res['remplacements'][0]['montant_ht_mad'], 30000.0)

    def test_aucune_ligne_onduleur_omission_nommee(self):
        res = eco.flux_ci(_base(), production_annee1_kwh=100000)
        self.assertEqual(res['remplacements'], [])
        motifs = {o['cle']: o['motif'] for o in res['flux_ht']['omissions']}
        self.assertEqual(motifs['remplacements'], eco.MOTIF_SANS_ONDULEUR)


class TauxClientTest(SimpleTestCase):
    def test_sans_taux_van_null_motif_tri_et_retour_publies(self):
        res = eco.flux_ci(_base(), production_annee1_kwh=100000)
        ind = res['indicateurs']
        self.assertIsNone(ind['van_mad'])
        self.assertEqual(ind['van_motif'], eco.MOTIF_VAN_OMISE)
        self.assertIsNotNone(ind['tri_pct'])
        self.assertIsNotNone(ind['retour_ans'])
        # LCOE non actualisé, étiqueté : coût total ÷ production totale.
        self.assertFalse(ind['lcoe_actualise'])
        production = sum(100000 * 0.995 ** (t - 1) for t in range(1, 26))
        self.assertAlmostEqual(ind['lcoe_mad_kwh'], 400000 / production,
                               places=5)

    def test_taux_client_ouvre_la_van(self):
        res = eco.flux_ci(_base(), production_annee1_kwh=100000,
                          taux_actualisation_client={
                              'valeur_pct': 8.0, 'source': 'DAF du client',
                              'saisi_le': '2026-09-20'})
        self.assertIsNotNone(res['indicateurs']['van_mad'])
        self.assertIsNone(res['indicateurs']['van_motif'])
        self.assertTrue(res['indicateurs']['lcoe_actualise'])

    def test_taux_sans_source_refuse(self):
        with self.assertRaises(eco.SaisieEconomieCiInvalide) as ctx:
            eco.flux_ci(_base(), taux_actualisation_client={
                'valeur_pct': 8.0, 'source': ''})
        self.assertEqual(ctx.exception.champ,
                         'taux_actualisation_client.source')


class OmTest(SimpleTestCase):
    def test_optionnelle_non_activee_non_deduite(self):
        res = eco.flux_ci(_base(), production_annee1_kwh=100000,
                          om={'activee': False, 'ht': 5000.0, 'ttc': 6000.0})
        self.assertEqual(res['om']['statut'], 'propose')
        self.assertEqual(res['om']['source'], eco.MOTIF_OM_PROPOSE)
        an1 = res['flux_ht']['flux'][1]
        self.assertEqual(an1['flux_mad'], an1['economie_mad'])
        motifs = {o['cle']: o['motif'] for o in res['flux_ht']['omissions']}
        self.assertEqual(motifs['charges_annuelles_mad'],
                         eco.MOTIF_OM_PROPOSE)

    def test_souscrite_deduite_dans_sa_base(self):
        res = eco.flux_ci(_base(), production_annee1_kwh=100000,
                          om={'activee': True, 'ht': 5000.0, 'ttc': 6000.0})
        self.assertEqual(res['om']['statut'], 'souscrit')
        an1 = res['flux_ht']['flux'][1]
        self.assertAlmostEqual(an1['economie_mad'] - an1['flux_mad'], 5000.0)

    def test_activee_sans_prix_tarif_a_renseigner(self):
        res = eco.flux_ci(_base(), production_annee1_kwh=100000,
                          om={'activee': True, 'ht': None, 'ttc': None})
        self.assertEqual(res['om']['statut'], 'tarif_a_renseigner')


class EntretienMinimumTest(SimpleTestCase):
    """AMOT96 (D-ACI-14=a) — sans O&M souscrite chiffrée, l'entretien minimum
    du réglage société (MAD HT/kWc/an × kWc retenu) est déduit de CHAQUE année
    du flux (jamais en double avec l'O&M) ; réglage vide ⇒ flux inchangé et
    « entretien non chiffré »."""

    REGLAGE = {'mad_kwc_an': 30, 'tva_pct': 20}
    APERCU = {'taille': {'retenue_kwc': 200}}

    def _entretien(self):
        return eco.entretien_minimum(self.REGLAGE, self.APERCU)

    def test_trente_mad_par_kwc_sur_deux_cents_kwc(self):
        self.assertEqual(self._entretien(), {'ht': 6000.0, 'ttc': 7200.0,
                                             'mad_kwc_an': 30.0,
                                             'kwc': 200.0})
        sans = eco.flux_ci(_base(), production_annee1_kwh=100000)
        res = eco.flux_ci(_base(), production_annee1_kwh=100000,
                          entretien=self._entretien())
        for ligne in res['flux_ht']['flux'][1:]:
            with self.subTest(annee=ligne['annee']):
                self.assertAlmostEqual(
                    ligne['economie_mad'] - ligne['flux_mad'], 6000.0,
                    places=1)
        self.assertEqual(res['entretien']['statut'], 'deduit')
        self.assertEqual(res['entretien']['montant_mad_an'], 6000.0)
        self.assertEqual(res['entretien']['source'],
                         eco.SOURCE_ENTRETIEN_MINIMUM)
        # Le retour et le TRI en tiennent compte (recalcul indépendant).
        cumul, retour = -400000.0, None
        for t in range(1, 26):
            cumul += 80000.0 * 0.995 ** (t - 1) - 6000.0
            if retour is None and cumul >= 0:
                retour = t
        self.assertEqual(res['indicateurs']['retour_ans'], retour)
        self.assertLess(res['indicateurs']['tri_pct'],
                        sans['indicateurs']['tri_pct'])

    def test_base_deux_ttc_a_la_tva_du_profil(self):
        res = eco.flux_ci(_base('inconnu'), production_annee1_kwh=100000,
                          entretien=self._entretien())
        an1 = res['flux_ttc']['flux'][1]
        self.assertAlmostEqual(an1['economie_mad'] - an1['flux_mad'], 7200.0,
                               places=1)

    def test_om_souscrite_seule_deduite_jamais_les_deux(self):
        res = eco.flux_ci(_base(), production_annee1_kwh=100000,
                          om={'activee': True, 'ht': 5000.0, 'ttc': 6000.0},
                          entretien=self._entretien())
        an1 = res['flux_ht']['flux'][1]
        self.assertAlmostEqual(an1['economie_mad'] - an1['flux_mad'], 5000.0)
        self.assertEqual(res['om']['statut'], 'souscrit')
        self.assertIsNone(res['entretien'])

    def test_om_proposee_l_entretien_minimum_est_deduit(self):
        res = eco.flux_ci(_base(), production_annee1_kwh=100000,
                          om={'activee': False, 'ht': 5000.0, 'ttc': 6000.0},
                          entretien=self._entretien())
        an1 = res['flux_ht']['flux'][1]
        self.assertAlmostEqual(an1['economie_mad'] - an1['flux_mad'], 6000.0)
        self.assertEqual(res['om']['statut'], 'propose')
        self.assertEqual(res['entretien']['statut'], 'deduit')

    def test_reglage_vide_flux_inchange_entretien_non_chiffre(self):
        self.assertIsNone(eco.entretien_minimum(None, self.APERCU))
        self.assertIsNone(eco.entretien_minimum(self.REGLAGE, {}))
        sans = eco.flux_ci(_base(), production_annee1_kwh=100000)
        res = eco.flux_ci(_base(), production_annee1_kwh=100000,
                          entretien=None)
        self.assertEqual(res['flux_ht']['flux'], sans['flux_ht']['flux'])
        self.assertEqual(res['entretien'], {
            'statut': 'non_chiffre', 'montant_mad_an': None,
            'source': eco.MOTIF_ENTRETIEN_NON_CHIFFRE})

    def test_assemblage_lit_le_reglage_et_le_kwc_de_l_etude(self):
        import copy
        import json
        from pathlib import Path
        contrats = Path(__file__).resolve().parents[1] / 'contract_samples'
        apercu = copy.deepcopy(json.loads(
            (contrats / 'etude_ci_preview.json').read_text(
                encoding='utf-8'))['exemple'])
        kwc = apercu['taille']['retenue_kwc']
        bloc = eco.assembler_economie_ci(
            apercu, tarif_declare={'contrat': 'bt_patente'},
            investissement={'ht': 900000.0, 'ttc': 1080000.0},
            mode_installation='commercial',
            reglages={'entretien_minimum': self.REGLAGE})
        self.assertEqual(bloc['entretien']['montant_mad_an'], 30.0 * kwc)
        an1 = bloc['flux_ht']['flux'][1]
        self.assertAlmostEqual(an1['economie_mad'] - an1['flux_mad'],
                               30.0 * kwc, places=1)
        public = eco.economie_ci_publique(bloc)
        self.assertEqual(public['entretien'], bloc['entretien'])


class ReventeHorsFluxTest(SimpleTestCase):
    def test_une_revente_ne_change_pas_le_retour(self):
        import inspect
        self.assertNotIn('revente', inspect.signature(eco.flux_ci).parameters)
        sans = eco.flux_ci(_base(), production_annee1_kwh=100000)
        base = _base()
        base['revente'] = {'statut': 'calculee', 'valeur_mad_an': 3600.0}
        avec = eco.flux_ci(base, production_annee1_kwh=100000)
        self.assertEqual(avec['indicateurs']['retour_ans'],
                         sans['indicateurs']['retour_ans'])
        self.assertEqual(avec['flux_ht']['flux'], sans['flux_ht']['flux'])


class BaseDeuxTest(SimpleTestCase):
    def test_inconnu_deux_flux_et_jalons_ttc(self):
        res = eco.flux_ci(_base('inconnu'), production_annee1_kwh=100000,
                          kwh_evites_an=50000)
        self.assertIsNotNone(res['flux_ht'])
        self.assertIsNotNone(res['flux_ttc'])
        self.assertEqual(len(res['jalons_ttc']), 5)
        self.assertEqual(res['flux_ttc']['flux'][0]['flux_mad'], -480000.0)
        self.assertEqual(res['indicateurs']['tarif_kwh_evite_moyen'], 1.6)
