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

    def test_cec14_taux_non_fini_refuse_nomme(self):
        for brut in (float('inf'), 1e300, float('nan')):
            with self.assertRaises(eco.SaisieEconomieCiInvalide) as ctx:
                eco.lire_taux_client({'valeur_pct': brut, 'source': 'client'})
            self.assertEqual(ctx.exception.champ,
                             'taux_actualisation_client.valeur_pct')

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

    def test_cec1_om_souscrite_hors_investissement_de_l_annee_zero(self):
        """CEC1 — une ligne O&M souscrite (charge annuelle) ne compte pas
        aussi dans l'investissement : jamais deux fois la première année."""
        import copy
        import json
        from pathlib import Path
        contrats = Path(__file__).resolve().parents[1] / 'contract_samples'
        apercu = copy.deepcopy(json.loads(
            (contrats / 'etude_ci_preview.json').read_text(
                encoding='utf-8'))['exemple'])
        apercu['composition'] = {}  # tout le dimensionné est au devis
        lignes = [{'designation': 'Panneau', 'ht': 850000.0, 'ttc': 1020000.0,
                   'optionnelle': False, 'onduleur': False, 'panneau': True},
                  {'designation': 'Onduleur', 'ht': 50000.0, 'ttc': 60000.0,
                   'optionnelle': False, 'onduleur': True},
                  {'designation': 'Contrat O&M', 'ht': 5000.0, 'ttc': 6000.0,
                   'optionnelle': False, 'onduleur': False,
                   'role_ci': 'om_ci'}]

        def _an0(controle, reglages=None):
            bloc = eco.assembler_economie_ci(
                apercu, tarif_declare={'contrat': 'bt_patente'},
                investissement={'ht': 905000.0, 'ttc': 1086000.0},
                lignes=lignes, mode_installation='commercial',
                controle_lignes=controle, reglages=reglages)
            return bloc['flux_ht']['flux'][0]['flux_mad']
        self.assertAlmostEqual(_an0(True), -900000.0)
        # L'aperçu du générateur (sans contrôle des lignes) : même chiffre.
        self.assertAlmostEqual(_an0(False), -900000.0)
        # Règles d'origine (devis déjà envoyé) : le calcul d'hier.
        self.assertAlmostEqual(
            _an0(True, {'regles_origine': True}), -905000.0)

    def test_om_quantite_differente_de_un_alerte_interne(self):
        """CEC9 — quantité O&M ≠ 1 : dite au vendeur, jamais servie."""
        from apps.ventes import economie_ci_options as opt
        lignes = [{'designation': 'Contrat O&M', 'ht': 30000.0, 'ttc': 36000.0,
                   'quantite': 5.0, 'optionnelle': False, 'role_ci': 'om_ci'},
                  {'designation': 'Contrat O&M bis', 'ht': 6000.0,
                   'ttc': 7200.0, 'quantite': 1.0, 'optionnelle': False,
                   'role_ci': 'om_ci'}]
        alertes = opt.alertes_om(lignes)
        self.assertEqual([a['code'] for a in alertes], ['om_quantite'])
        self.assertIn('Contrat O&M', alertes[0]['message'])
        self.assertTrue(alertes[0]['interne'])

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


class _FicheModule:
    """Double d'une ``FicheTechnique`` de module (lue par la façade
    ``stock.selectors``) : tout champ non posé vaut NULL."""
    type_fiche = 'module'

    def __init__(self, **champs):
        self.__dict__.update(champs)

    def __getattr__(self, nom):
        return None


class _Produit:
    def __init__(self, fiche=None, nom='Module'):
        self.nom = nom
        if fiche is not None:
            self.fiche_technique = fiche


class DegradationFicheModuleTest(SimpleTestCase):
    """AMOT99 (D-ACI-18=a) — la dégradation suit la courbe de garantie de la
    fiche module (perte de la 1re année puis taux annuel LINÉAIRE) ; fiche
    muette ⇒ le défaut 0,5 %/an, dit « défaut, fiche muette ». Recalculs
    indépendants : année 1 = 1, année t ≥ 2 = 1 − perte an 1 − taux × (t − 2).
    Test-du-test : un taux constant (0,995^(t−1) ou 0,996^(t−1)) rend
    l'année 2 fausse (0,99 attendu)."""

    FICHE = {'degradation_annuelle_pct': '0.40',
             'degradation_annee1_pct': '1.00'}

    def _courbe(self, *fiches):
        from apps.ventes.moteur_ci import degradation
        return degradation.courbe_depuis_fiches(list(fiches))

    def test_flux_suit_la_courbe_de_la_fiche(self):
        res = eco.flux_ci(_base(), production_annee1_kwh=100000,
                          degradation=self._courbe(self.FICHE))
        lignes = {f['annee']: f for f in res['flux_ht']['flux']}
        cumul = -400000.0
        for t in range(1, 26):
            facteur = 1.0 if t == 1 else 1.0 - 0.01 - 0.004 * (t - 2)
            cumul += 80000.0 * facteur
            with self.subTest(annee=t):
                self.assertAlmostEqual(lignes[t]['economie_mad'],
                                       80000.0 * facteur, places=1)
                self.assertEqual(lignes[t]['production_kwh'],
                                 round(100000 * facteur))
        self.assertEqual(lignes[2]['production_kwh'], 99000)
        self.assertEqual(lignes[25]['production_kwh'], 89800)
        self.assertAlmostEqual(lignes[25]['cumul_mad'], cumul, places=1)
        # Le LCOE non actualisé lit la MÊME courbe.
        energie = sum(100000 * (1.0 if t == 1 else 0.99 - 0.004 * (t - 2))
                      for t in range(1, 26))
        self.assertAlmostEqual(res['indicateurs']['lcoe_mad_kwh'],
                               400000 / energie, places=5)

    def test_hypotheses_nomment_la_fiche(self):
        from apps.ventes.moteur_ci import degradation
        bloc = eco.flux_ci(_base(), production_annee1_kwh=100000,
                           degradation=self._courbe(self.FICHE))['flux_ht']
        hyp = {h['cle']: h for h in bloc['hypotheses']}
        self.assertEqual(hyp['degradation_pct']['valeur'], 0.4)
        self.assertEqual(hyp['degradation_pct']['source'],
                         degradation.SOURCE_FICHE)
        self.assertEqual(hyp['degradation_pct']['source_code'],
                         'degradation_fiche_module')
        self.assertEqual(hyp['degradation_annee1_pct']['valeur'], 1.0)
        self.assertEqual(hyp['degradation_annee1_pct']['source'],
                         degradation.SOURCE_FICHE)

    def test_fiche_muette_defaut_cinq_dixiemes_dit(self):
        from apps.ventes.moteur_ci import degradation
        for courbe in (self._courbe(), self._courbe({}),
                       self._courbe({'degradation_annee1_pct': '1.0'})):
            res = eco.flux_ci(_base(), production_annee1_kwh=100000,
                              degradation=courbe)
            hyp = {h['cle']: h for h in res['flux_ht']['hypotheses']}
            self.assertEqual(hyp['degradation_pct']['valeur'], 0.5)
            self.assertEqual(hyp['degradation_pct']['source'],
                             degradation.SOURCE_DEFAUT)
            self.assertEqual(hyp['degradation_pct']['source_code'],
                             'degradation_defaut_fiche_muette')
            self.assertNotIn('degradation_annee1_pct', hyp)
            # Mêmes chiffres qu'hier (0,995^(t−1)) : seule la source change.
            lignes = {f['annee']: f['production_kwh']
                      for f in res['flux_ht']['flux']}
            for t in range(1, 26):
                self.assertEqual(lignes[t], round(100000 * 0.995 ** (t - 1)))

    def test_sans_courbe_le_calcul_d_hier(self):
        """Devis aux règles d'origine : aucune courbe passée ⇒ la source
        NREL d'hier, octet pour octet."""
        sans = eco.flux_ci(_base(), production_annee1_kwh=100000)
        hyp = {h['cle']: h for h in sans['flux_ht']['hypotheses']}
        self.assertEqual(hyp['degradation_pct']['source'],
                         eco.DEGRADATION_CI_SOURCE)
        self.assertNotIn('degradation_annee1_pct', hyp)

    def test_premiere_annee_non_publiee_taux_de_la_fiche(self):
        from apps.ventes.moteur_ci import degradation
        courbe = self._courbe({'degradation_annuelle_pct': '0.55'})
        self.assertEqual(courbe['annee1_pct'], 0.55)
        self.assertEqual(courbe['source_annee1'],
                         degradation.SOURCE_FICHE_SANS_ANNEE1)
        res = eco.flux_ci(_base(), production_annee1_kwh=100000,
                          degradation=courbe)
        lignes = {f['annee']: f['production_kwh']
                  for f in res['flux_ht']['flux']}
        self.assertEqual(lignes[2], round(100000 * (1 - 0.0055)))
        self.assertEqual(lignes[3], round(100000 * (1 - 0.0055 * 2)))

    def test_plusieurs_fiches_la_plus_penalisante(self):
        courbe = self._courbe(self.FICHE, {'degradation_annuelle_pct': '0.55',
                                           'degradation_annee1_pct': '2'})
        self.assertEqual((courbe['annuelle_pct'], courbe['annee1_pct']),
                         (0.55, 2.0))

    def test_comparaison_cse_meme_courbe(self):
        res = eco.flux_ci(_base(), production_annee1_kwh=100000,
                          degradation=self._courbe(self.FICHE))
        cse = eco.comparaison_cse(res['flux_ht'], {
            'tarif_kwh_ht': 0.9, 'duree_ans': 20, 'source': 'offre écrite'},
            100000)
        kwh = {a['annee']: a['kwh_livres'] for a in cse['annees']}
        self.assertEqual(kwh[1], 100000)
        self.assertEqual(kwh[2], 99000)

    def test_courbe_lue_sur_la_fiche_du_produit(self):
        """La façade ``stock.selectors`` : seules les fiches MODULE comptent ;
        aucun module ⇒ défaut, fiche muette."""
        from decimal import Decimal

        from apps.ventes.domain.etude_ci import courbe_degradation_des_produits
        from apps.ventes.moteur_ci import degradation
        module = _Produit(_FicheModule(
            degradation_annuelle_pct=Decimal('0.40'),
            degradation_annee1_pct=Decimal('1.00')))
        onduleur = _Produit(_FicheModule(
            type_fiche='onduleur', degradation_annuelle_pct=Decimal('5')))
        courbe = courbe_degradation_des_produits([module, onduleur, None,
                                                  _Produit()])
        self.assertEqual((courbe['annuelle_pct'], courbe['annee1_pct'],
                          courbe['source']),
                         (0.4, 1.0, degradation.SOURCE_FICHE))
        muette = courbe_degradation_des_produits([onduleur, _Produit()])
        self.assertEqual(muette['source'], degradation.SOURCE_DEFAUT)

    def test_regles_d_origine_aucune_courbe(self):
        """``economie_ci_pour_devis`` : la courbe n'est posée que sur un
        NOUVEAU rendu (``calcul_corrige``) ; un devis envoyé garde hier."""
        from types import SimpleNamespace
        from unittest import mock
        devis = SimpleNamespace(etude_params={}, mode_installation='industriel')
        for corrige in (True, False):
            with mock.patch('apps.ventes.domain.regles_calcul.calcul_corrige',
                            return_value=corrige), \
                    mock.patch('apps.ventes.utils.options.option_totaux',
                               return_value={'ht': 1.0, 'ttc': 1.2}), \
                    mock.patch.object(eco, 'reglages_economie_ci',
                                      return_value={}), \
                    mock.patch.object(eco, 'lignes_pour_economie_ci',
                                      return_value=[]), \
                    mock.patch('apps.ventes.domain.etude_ci.'
                               'courbe_degradation_du_devis',
                               return_value={'courbe': 'fiche'}), \
                    mock.patch.object(eco, 'assembler_economie_ci') as assem:
                eco.economie_ci_pour_devis(devis, None)
            reglages = assem.call_args.kwargs['reglages']
            with self.subTest(corrige=corrige):
                if corrige:
                    self.assertEqual(reglages['degradation_module'],
                                     {'courbe': 'fiche'})
                else:
                    self.assertNotIn('degradation_module', reglages)

    def test_libelles_francais_egaux_au_texte_servi(self):
        from apps.ventes.moteur_ci import degradation
        from apps.ventes.quote_engine import i18n_labels
        for source, code in degradation.CODES_SOURCES.items():
            libelle = i18n_labels.LIBELLES[f'ci_code_{code}']
            self.assertEqual(libelle['fr'], source)
            self.assertTrue(libelle['en'] and libelle['ar'])


class SaisieFacultativeInvalideTest(SimpleTestCase):
    def test_cec14_offre_invalide_ecartee_economie_gardee(self):
        """CEC14 — à la lecture d'un devis, une offre de prêteur sans source
        n'efface plus l'économie : elle est écartée et dite au vendeur."""
        import copy
        import json
        from pathlib import Path

        from apps.ventes import economie_ci_options as opt
        contrats = Path(__file__).resolve().parents[1] / 'contract_samples'
        apercu = copy.deepcopy(json.loads(
            (contrats / 'etude_ci_preview.json').read_text(
                encoding='utf-8'))['exemple'])
        saisies = {'offre_financement': {'nature': 'credit'}}
        kw = dict(tarif_declare={'contrat': 'bt_patente'},
                  investissement={'ht': 900000.0, 'ttc': 1080000.0},
                  mode_installation='commercial')
        with self.assertRaises(eco.SaisieEconomieCiInvalide):
            eco.assembler_economie_ci(apercu, saisies=saisies, **kw)
        bloc = opt.sans_saisie_invalide(eco.assembler_economie_ci, apercu,
                                        saisies=saisies, **kw)
        self.assertEqual(bloc['statut'], eco.STATUT_CALCULE)
        self.assertIn('saisie_ecartee',
                      [a['code'] for a in bloc['alertes_internes']])
        self.assertNotIn('alertes_internes', eco.economie_ci_publique(bloc))
        # Devis envoyé sous le niveau 3 : le refus d'hier, inchangé.
        with self.assertRaises(eco.SaisieEconomieCiInvalide):
            opt.sans_saisie_invalide(eco.assembler_economie_ci, apercu,
                                     saisies=saisies,
                                     reglages={'regles_origine': True}, **kw)


class OptionAvecBatterieTest(SimpleTestCase):
    """CEC3 — l'option « avec batterie » se chiffre par le MÊME flux que
    l'option « sans » (jamais total ÷ économie an 1), batterie remplacée au
    montant de sa ligne."""
    LIGNES = [
        {'designation': 'Onduleur hybride SUN-12K', 'ht': 40000.0,
         'ttc': 48000.0, 'optionnelle': False, 'onduleur': True},
        {'designation': 'Batterie Dyness 10 kWh', 'ht': 60000.0,
         'ttc': 72000.0, 'optionnelle': False, 'onduleur': False},
    ]

    def test_meme_flux_plus_remplacement_batterie(self):
        from apps.ventes import economie_ci_options as opt
        sans = eco.flux_ci(_base(), production_annee1_kwh=100000,
                           onduleur={'ht': 40000.0, 'ttc': 48000.0})
        avec = opt.flux_option_avec(
            _base(), lignes=self.LIGNES, production_annee1_kwh=100000,
            batterie=opt.annee_remplacement_batterie(garantie_mois=120))
        flux = {f['annee']: f for f in avec['flux_ht']['flux']}
        ref = {f['annee']: f for f in sans['flux_ht']['flux']}
        self.assertAlmostEqual(ref[11]['flux_mad'] - flux[11]['flux_mad'],
                               60000.0, places=1)
        self.assertEqual(flux[5]['flux_mad'], ref[5]['flux_mad'])
        self.assertEqual([r['composant'] for r in avec['remplacements']],
                         ['onduleur', 'batterie'])
        self.assertLess(avec['indicateurs']['tri_pct'],
                        sans['indicateurs']['tri_pct'])

    def test_retour_au_dixieme_interpole(self):
        from apps.ventes import economie_ci_options as opt
        res = eco.flux_ci(_base(inv=400000.0, economie=90000.0),
                          production_annee1_kwh=100000)
        dixieme = opt.retour_au_dixieme(res['flux_ht'])
        self.assertLessEqual(dixieme, res['indicateurs']['retour_ans'])
        self.assertGreater(dixieme, res['indicateurs']['retour_ans'] - 1)

    def test_annee_batterie_la_plus_prudente_sinon_defaut_etiquete(self):
        from apps.ventes import economie_ci_options as opt
        self.assertEqual(opt.annee_remplacement_batterie(120, 6000)['annee'],
                         11)
        self.assertEqual(opt.annee_remplacement_batterie(120, 3000)['annee'],
                         9)
        defaut = opt.annee_remplacement_batterie()
        self.assertEqual(defaut['annee'], 11)
        self.assertIn('défaut fondateur', defaut['source'])

    # ── Niveau 13 (fondateur 19/11/2026) : « cycles publiés, usage réel » ──
    BILAN_0080 = {'batterie': {'capacite_utile_kwh': 45.81, 'restitue_kwh_an': 13239,
                               'charge_kwh_an': 13510, 'rendement': 0.98}}

    def test_cycles_par_an_du_bilan_une_seule_formule(self):
        from apps.ventes import economie_ci_options as opt
        self.assertAlmostEqual(opt.cycles_par_an_du_bilan(self.BILAN_0080), 13239 / 45.81)
        for bilan in (None, {}, {'batterie': None}, {'batterie': {'capacite_utile_kwh': 45.81}},
                      {'batterie': {'capacite_utile_kwh': 0, 'restitue_kwh_an': 100}},
                      {'batterie': {'capacite_utile_kwh': 45.81, 'restitue_kwh_an': 0}},
                      {'batterie': {'capacite_utile_kwh': 'x', 'restitue_kwh_an': 100}}):
            self.assertIsNone(opt.cycles_par_an_du_bilan(bilan), bilan)

    def test_niveau_13_cycles_publies_sur_usage_reel_garantie_pas_un_plafond(self):
        from apps.ventes import economie_ci_options as opt
        par_an = opt.cycles_par_an_du_bilan(self.BILAN_0080)       # ≈ 289
        regle = opt.annee_remplacement_batterie(120, 8000, cycles_par_an=par_an)
        self.assertEqual(regle['annee'], 28)                        # ⌊8000 ÷ 289⌋ + 1
        self.assertEqual(regle['duree'], {'cycles_publies': 8000, 'cycles_par_an': 289})
        self.assertEqual(regle['source'], "8000 cycles publiés par le fabricant, 289 cycles "
                                          "par an d'après l'étude")
        # Usage intense : les cycles fixent une année AVANT la garantie.
        self.assertEqual(opt.annee_remplacement_batterie(120, 3000, cycles_par_an=400)['annee'], 8)

    def test_niveau_13_sans_cycles_ou_sans_usage_regle_d_hier_a_l_identique(self):
        from apps.ventes import economie_ci_options as opt
        for args in ((120, 6000), (120, 3000), (120, None), (None, 6000), (None, None)):
            hier = opt.annee_remplacement_batterie(*args)
            self.assertEqual(opt.annee_remplacement_batterie(*args, cycles_par_an=None), hier)
            self.assertEqual(opt.annee_remplacement_batterie(*args, cycles_par_an=0), hier)
            self.assertNotIn('duree', hier)
        # Pas de cycles publiés : fin de garantie + 1 ; ni l'un ni l'autre : le défaut.
        self.assertEqual(opt.annee_remplacement_batterie(120, None, cycles_par_an=289),
                         opt.annee_remplacement_batterie(120))
        self.assertEqual(opt.annee_remplacement_batterie(cycles_par_an=289),
                         opt.annee_remplacement_batterie())

    def test_niveau_13_flux_sans_remplacement_et_batterie_duree_servie(self):
        from apps.ventes import economie_ci_options as opt
        regle = opt.annee_remplacement_batterie(120, 8000, cycles_par_an=13239 / 45.81)
        avec = opt.flux_option_avec(_base(), lignes=self.LIGNES, production_annee1_kwh=100000,
                                    batterie=regle)
        self.assertEqual([r['composant'] for r in avec['remplacements']], ['onduleur'])
        self.assertEqual(avec['batterie_duree'], {'cycles_publies': 8000, 'cycles_par_an': 289,
                                                  'annee_remplacement': None,
                                                  'horizon_ans': eco.HORIZON_CI_ANS})
        self.assertIn('batterie_duree', eco.economie_ci_publique(avec))
        # Dans l'horizon : remplacement compté ET année servie.
        dedans = opt.flux_option_avec(_base(), lignes=self.LIGNES, production_annee1_kwh=100000,
                                      batterie=opt.annee_remplacement_batterie(
                                          120, 6000, cycles_par_an=400))
        self.assertEqual(dedans['batterie_duree']['annee_remplacement'], 16)
        self.assertEqual([r['annee'] for r in dedans['remplacements']
                          if r['composant'] == 'batterie'], [16])
        # Règle d'hier : aucune clé neuve.
        hier = opt.flux_option_avec(_base(), lignes=self.LIGNES, production_annee1_kwh=100000,
                                    batterie=opt.annee_remplacement_batterie(120, 8000))
        self.assertNotIn('batterie_duree', hier)

    def test_base_deux_jalons_ttc_suivent_le_remplacement(self):
        from apps.ventes import economie_ci_options as opt
        base = _base(tva='inconnu')
        sans = eco.flux_ci(base, production_annee1_kwh=100000,
                           onduleur={'ht': 40000.0, 'ttc': 48000.0})
        avec = opt.flux_option_avec(base, lignes=self.LIGNES,
                                    production_annee1_kwh=100000)
        j_sans = {j['annee']: j['cumul_mad'] for j in sans['jalons_ttc']}
        j_avec = {j['annee']: j['cumul_mad'] for j in avec['jalons_ttc']}
        self.assertAlmostEqual(j_sans[15] - j_avec[15], 72000.0, places=1)
        self.assertEqual(j_sans[10], j_avec[10])
        # Mêmes post-traitements que l'option « sans » (coût du kWh servi).
        self.assertIsNotNone(avec['indicateurs']['lcoe_mad_kwh'])

    def test_remplacement_au_dela_de_l_horizon_aucun_ajout(self):
        from apps.ventes import economie_ci_options as opt
        avec = opt.flux_option_avec(
            _base(), lignes=self.LIGNES, production_annee1_kwh=100000,
            batterie=opt.annee_remplacement_batterie(cycles_publies=10000))
        self.assertEqual([r['composant'] for r in avec['remplacements']],
                         ['onduleur'])

    def test_cec11_batterie_rack_ou_support_inclus_reste_une_batterie(self):
        from apps.ventes import economie_ci_options as opt
        for nom in ('Batterie lithium rack 30 kWh',
                    'Batterie Dyness 10 kWh (support mural inclus)'):
            self.assertTrue(opt._est_batterie({'designation': nom}), nom)
        self.assertFalse(opt._est_batterie(
            {'designation': 'Support mural pour batterie'}))

    def test_seule_la_batterie_est_remplacee(self):
        from apps.ventes import economie_ci_options as opt
        lignes = self.LIGNES + [
            {'designation': 'Câble batterie 35 mm²', 'ht': 1000.0,
             'ttc': 1200.0, 'optionnelle': False, 'onduleur': False},
            {'designation': 'Onduleur hybride compatible batterie',
             'ht': 5000.0, 'ttc': 6000.0, 'optionnelle': False,
             'onduleur': True}]
        avec = opt.flux_option_avec(_base(), lignes=lignes,
                                    production_annee1_kwh=100000)
        batterie = [r for r in avec['remplacements']
                    if r['composant'] == 'batterie']
        self.assertEqual(batterie[0]['montant_ht_mad'], 60000.0)


class ReglagesSansTariffSettingsTest(SimpleTestCase):
    def test_cec7_sans_reglage_les_scenarios_que_le_bareme_seede(self):
        """CEC7 — une société sans réglage lit les scénarios seedés : le même
        devis ne change plus d'économie selon que le PDF a déjà été rendu."""
        from unittest import mock
        from apps.parametres.tariff import SENSIBILITES_CI_DEFAUT
        with mock.patch('apps.parametres.models_company.CompanyProfile.objects') as profil, \
                mock.patch('apps.parametres.models_tariff.TariffSettings.objects') as reglage:
            profil.filter.return_value.values_list.return_value.first.return_value = None
            reglage.filter.return_value.first.return_value = None
            lus = eco.reglages_economie_ci(object())
        self.assertEqual(lus['sensibilites_ci'],
                         [dict(s) for s in SENSIBILITES_CI_DEFAUT])


# ═════════════════════════════════════════════════════════════════════════════
# Niveau 13 (fondateur 19/11/2026, D-BATCYC-1) — « cycles publiés, usage réel » :
# le remplacement de la batterie de l'option « avec » sur le flux 25 ans. Les
# jeux de données sont ceux de ``test_ciq120_devis_auto_ci`` (fichier-mur : ces
# tests vivent ici, avec le flux qu'ils éprouvent).
# ═════════════════════════════════════════════════════════════════════════════
from unittest import mock  # noqa: E402 — bloc ajouté en fin de module

from apps.ventes.tests import test_ciq120_devis_auto_ci as ciq120  # noqa: E402


class RemplacementCyclesNiveau13FluxTests(ciq120.RetourOptionAvecFluxTests):
    """Le bloc de l'option, la montée de la banque et le verdict lisent la même
    année (jeux de ``RetourOptionAvecFluxTests``, sans rejouer ses tests)."""

    # ── Niveau 13 (fondateur 19/11/2026) : « cycles publiés, usage réel » ──
    FICHE_8000 = {'garantie_mois': 120, 'cycles_publies': 8000.0}
    BILAN_0080 = {'production_kwh': 80000.0, 'batterie': {
        'capacite_utile_kwh': 45.81, 'restitue_kwh_an': 13239, 'charge_kwh_an': 13510,
        'rendement': 0.98}}

    def _evaluation_0080(self):
        return dict(self._evaluation(), bilan=dict(self.BILAN_0080))

    def test_niveau_13_bloc_sans_remplacement_batterie_niveau_12_annee_11(self):
        from apps.ventes.domain.etude_ci_batterie import _bloc
        blocs = {niveau: _bloc(self._evaluation_0080(), self._Valoriseur(),
                               dict(self._ctx(), batterie=self.FICHE_8000, regles_cycles=niveau))
                 for niveau in (True, False)}
        flux = blocs[True]['economie_flux']
        self.assertEqual([r['composant'] for r in flux['remplacements']], ['onduleur'])
        self.assertEqual(flux['batterie_duree'], {'cycles_publies': 8000, 'cycles_par_an': 289,
                                                  'annee_remplacement': None, 'horizon_ans': 25})
        hier = blocs[False]['economie_flux']
        self.assertEqual([(r['composant'], r['annee']) for r in hier['remplacements']
                          if r['composant'] == 'batterie'], [('batterie', 11)])
        self.assertNotIn('batterie_duree', hier)
        # Le cumul net à 25 ans ne porte plus le prix de la batterie (4 × 60 000 HT).
        self.assertAlmostEqual(flux['flux_ht']['flux'][-1]['cumul_mad']
                               - hier['flux_ht']['flux'][-1]['cumul_mad'], 240000.0, delta=1)
        # Sans contexte de devis (aperçu) : les règles courantes.
        defaut = _bloc(self._evaluation_0080(), self._Valoriseur(),
                       dict(self._ctx(), batterie=self.FICHE_8000))['economie_flux']
        self.assertEqual(defaut['batterie_duree'], flux['batterie_duree'])

    def test_niveau_13_meme_annee_pour_le_flux_la_banque_et_le_verdict(self):
        """La montée de la banque (``_remplacement_moteur``), le verdict marginal
        (``_remplacement_du_bloc``, repli sans flux) et le flux lisent la MÊME
        année pour une évaluation et un niveau donnés — le bilan du candidat."""
        from apps.ventes.domain import etude_ci_batterie as m
        evaluation = self._evaluation_0080()
        for niveau, annee in ((True, None), (False, 11)):
            with self.subTest(niveau=niveau):
                _ht, moteur = m._remplacement_moteur(20, niveau)(evaluation, self.FICHE_8000)
                self.assertEqual(moteur, annee)
                self.assertEqual(m._remplacement_du_bloc(evaluation, {}, self.FICHE_8000, 20,
                                                         niveau)[1], annee)
                # Option des LIGNES : l'évaluation n'a pas de bilan, le bloc servi en a un.
                self.assertEqual(m._remplacement_du_bloc({'composition': {}},
                                                         {'bilan': dict(self.BILAN_0080)},
                                                         self.FICHE_8000, 20, niveau)[1], annee)
                bloc = m._bloc(evaluation, self._Valoriseur(),
                               dict(self._ctx(), batterie=self.FICHE_8000, regles_cycles=niveau))
                servie = [r['annee'] for r in bloc['economie_flux']['remplacements']
                          if r['composant'] == 'batterie']
                self.assertEqual(servie, [] if annee is None else [annee])
                self.assertEqual(m._remplacement_du_bloc(evaluation, bloc, self.FICHE_8000, 20,
                                                         niveau)[1], annee)
        # Un candidat qui cycle plus (petite banque) peut remplacer dans l'horizon.
        petit = dict(evaluation, bilan={'batterie': {'capacite_utile_kwh': 15.28,
                                                     'restitue_kwh_an': 5577}})   # 365 cycles
        self.assertEqual(m._remplacement_moteur(20, True)(petit, self.FICHE_8000)[1], 22)

    def test_niveau_13_atteint_le_flux_la_banque_et_le_verdict_des_deux_chemins(self):
        """``regles_cycles`` (niveau 13) passé à ``option_avec_de_l_etude`` atteint
        le contexte du flux (étude ET lignes), la montée de la banque et le verdict ;
        absent (aperçu, aucun devis) ⇒ règles courantes."""
        from apps.ventes.domain import etude_ci_batterie as m
        evaluation = self._evaluation()
        resultat = {'evaluation': evaluation, 'prix_a_renseigner': [], 'hypotheses': [],
                    'alertes': [], 'motif': None}
        catalogue = {'batterie': {'hybrides': [1], 'batteries': [{'produit': 1}]}}
        for niveau, attendu in ((False, False), (True, True), (None, True)):
            vus, verdicts = [], []
            kw = {} if niveau is None else {'regles_cycles': niveau}
            with mock.patch.object(m, 'batteries_compatibles', return_value=[1]), \
                    mock.patch.object(m, '_dimensionner', return_value=resultat) as dim, \
                    mock.patch.object(m, '_option_dominee', return_value=False), \
                    mock.patch.object(m, 'verdict_rentabilite',
                                      lambda *a: verdicts.append(a[-1])), \
                    mock.patch.object(m, '_bloc', lambda ev, val, ctx, **k: vus.append(ctx) or {}), \
                    mock.patch.object(m, '_option_imposee', lambda imp, ctx: vus.append(ctx) or {'k': 1}):
                for imposee in (None, {'x': 1}):
                    m.option_avec_de_l_etude(catalogue, {'kwc': 1}, choix='avec', lead=None,
                                             imposee=imposee, tva_recuperable={'valeur': 'inconnu'},
                                             **kw)
            with self.subTest(niveau=niveau):
                self.assertEqual([c['regles_cycles'] for c in vus], [attendu, attendu])
                self.assertEqual(dim.call_args.kwargs['regles_cycles'], attendu)
                self.assertEqual(verdicts, [attendu, attendu])

    def test_niveau_13_verdict_dit_si_le_remplacement_est_compte(self):
        """Le verdict « non rentable » ne compte plus un remplacement que le
        flux ne modélise pas : ``remplacement_inclus: False`` (niveau 13), clé
        ABSENTE au niveau 12 où l'année 11 le compte toujours."""
        from apps.ventes.domain import etude_ci_batterie as m
        sans = {'cout': 100000.0, 'economie': 20000.0}
        # Supplément de 240 000 HT pour 20 000 MAD/an de plus : 12 ans.
        evaluation = dict(self._evaluation_0080(), cout=340000.0, economie=40000.0)
        nouveau = m.verdict_rentabilite(sans, evaluation, {}, self.FICHE_8000, 20, True)
        self.assertEqual(nouveau['retour_marginal_ans'], 12.0)
        self.assertIs(nouveau['remplacement_inclus'], False)
        hier = m.verdict_rentabilite(sans, evaluation, {}, self.FICHE_8000, 20, False)
        self.assertNotIn('remplacement_inclus', hier)
        self.assertGreater(hier['retour_marginal_ans'], 12.0)

    def test_niveau_13_jeton_d_empreinte_des_lignes(self):
        """Un brouillon passé de 12 à 13 change d'empreinte : son étude est
        recalculée au prochain rafraîchissement ; un devis ≤ 12 garde la sienne."""
        from types import SimpleNamespace

        from apps.ventes.domain.etude_ci_batterie import _jeton_cycles
        self.assertEqual(_jeton_cycles([], SimpleNamespace(regles_calcul=12)), [])
        self.assertEqual(_jeton_cycles([], SimpleNamespace(regles_calcul=13)), ['cycles13'])
        # Niveau 14 (D-SENS-1) : un jeton de plus, les brouillons 13 → 14 sont recalculés.
        self.assertEqual(_jeton_cycles([], SimpleNamespace(regles_calcul=14)), ['cycles13', 'sensibilites14'])
        ligne = SimpleNamespace(devis=SimpleNamespace(regles_calcul=12))
        self.assertEqual(_jeton_cycles([ligne]), [])


class RemplacementCyclesNiveau13DevisTests(ciq120.OptionBatterieCITests):
    """Un devis au niveau 12 garde l'année 11 ; au niveau 13 l'année suit ses
    cycles (jeux de ``OptionBatterieCITests``, sans rejouer ses tests)."""

    def test_niveau_13_cycles_publies_niveau_12_garde_l_annee_11(self):
        """Décision fondateur du 19/11/2026 (« cycles publiés, usage réel ») —
        fiche Dyness à 8 000 cycles et 10 ans de garantie : un devis au niveau
        12 (envoyé) garde son remplacement en année 11 ; au niveau 13 l'année
        est ⌊8 000 ÷ cycles par an de SON bilan⌋ + 1, aucun remplacement au-delà
        de 25 ans, et la durée de vie est imprimée dans « Bases du calcul »."""
        from functools import partial

        from apps.ventes.economie_ci_options import cycles_par_an_du_bilan
        from apps.ventes.quote_engine.ci import blocs as ci_blocs
        from apps.ventes.quote_engine.ci.synthese import _argent_option_avec
        from apps.ventes.quote_engine.industriel.finance import rangees_hypotheses
        from apps.ventes.quote_engine.residential.theme import fmt
        ids = [self.b5.id, self.b10.id, self.b16.id]
        ciq120.Produit.objects.filter(pk__in=ids).update(garantie_mois=120)
        ciq120.FicheTechnique.objects.filter(produit_id__in=ids).update(bat_cycles_publies=8000)
        options = {}
        for niveau in (12, 13):
            devis = self._auto(self._boulangerie())
            ciq120.Devis.objects.filter(pk=devis.pk).update(regles_calcul=niveau)
            devis.refresh_from_db()
            with mock.patch.object(ciq120.tarif_ci, 'tarif_applicable', side_effect=ciq120._tarif_grille):
                ciq120.etude_ci.rafraichir_etude_ci_devis(devis, force=True)
            devis.refresh_from_db()
            self.assertEqual(devis.regles_calcul, niveau)
            options[niveau] = devis.etude_params['etude_ci']['option_avec']
            self.assertIsNotNone(options[niveau]['economie_flux'], niveau)

        def annees_batterie(option):
            return [r['annee'] for r in option['economie_flux']['remplacements']
                    if r['composant'] == 'batterie']
        self.assertEqual(annees_batterie(options[12]), [11])
        self.assertNotIn('batterie_duree', options[12]['economie_flux'])
        par_an = cycles_par_an_du_bilan(options[13]['bilan'])
        self.assertTrue(par_an and par_an > 0)
        annee = int(8000 // par_an) + 1
        dans = annee <= 25
        self.assertEqual(options[13]['economie_flux']['batterie_duree'], {
            'cycles_publies': 8000, 'cycles_par_an': int(round(par_an)),
            'annee_remplacement': annee if dans else None, 'horizon_ans': 25})
        self.assertEqual(annees_batterie(options[13]), [annee] if dans else [])
        # Imprimé (« Bases du calcul » : les rangées de la page finance et de la
        # page 3 commerciale), chaque nombre lu sur ``batterie_duree``.
        argent, _motif = _argent_option_avec(options[13], 'industriel')
        rangees = dict((libelle, valeur) for libelle, valeur in rangees_hypotheses(
            {}, {'argent': argent}, fmt, fmt, partial(ci_blocs.libelle, {})) if libelle)
        attendu = '%s cycles publiés, environ %s cycles par an' % (fmt(8000), fmt(round(par_an)))
        self.assertEqual(rangees['Durée de vie de la batterie'],
                         attendu if dans else attendu + ' — aucun remplacement sur 25 ans')
        argent_12, _motif = _argent_option_avec(options[12], 'industriel')
        self.assertNotIn('Durée de vie de la batterie', dict(rangees_hypotheses(
            {}, {'argent': argent_12}, fmt, fmt, partial(ci_blocs.libelle, {}))))


# ═════════════════════════════════════════════════════════════════════════════
# Niveau 14 (D-SENS-1, fondateur 19/11/2026 « Yes, fix it ») — les sensibilités
# de l'option « avec batterie » (``domain/sensibilites_option_avec.py``) : même
# forme, mêmes scénarios, production RE-SIMULÉE avec la batterie.
# ═════════════════════════════════════════════════════════════════════════════
_JOURS_MOIS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
_TARIF_MT_DECLARE = {
    'contrat': 'mt_general', 'base_tarifs': 'ht', 'provenance': 'facture', 'date_facture': '2026-08-31',
    'mt': {'tarif_pointe': 1.6, 'tarif_pleines': 1.1, 'tarif_creuses': 0.8}}
_CLOCHE = [0.0] * 6 + [0.1, 0.3, 0.5, 0.7, 0.85, 0.9, 0.9, 0.85, 0.7, 0.5, 0.3, 0.1] + [0.0] * 6
#: La forme d'une ligne du contrat ``economie_ci.json`` (option réseau, D-SENS-1 compris).
_CLES_LIGNE = {'cle', 'variation_pct', 'source', 'economie_annee1_mad', 'retour_ans', 'retour_dixieme_ans',
               'tri_pct', 'cumul_25_ans_mad', 'ecart_retour_ans', 'ecart_tri_pct'}


class SensibilitesOptionAvecNiveau14Tests(SimpleTestCase):
    """Une option « avec » de 15 kWc et 2 × 10 kWh utiles (6 000 cycles publiés)
    évaluée par LE moteur (``evaluer_option_avec`` + ``simuler_batterie_jour``)
    et valorisée par LA valorisation de l'étude (``etude_ci._valoriseur``)."""

    CHARGE = [{'mois': mo, 'type_jour': 'ouvre', 'nb_jours': n,
               'charge_kwh': [6.0 if 7 <= h < 19 else 4.0 for h in range(24)]}
              for mo, n in enumerate(_JOURS_MOIS, start=1)]
    PRODUCTION = [{'mois': mo, 'production_kwh_kwc': [v * (0.8 + 0.04 * abs(6.5 - mo)) for v in _CLOCHE]}
                  for mo in range(1, 13)]
    BANQUE = {'produit': 7, 'nom': 'Dyness 10', 'kwh_utile': 10.0, 'quantite': 2, 'rendement': 0.95,
              'garantie_mois': 120, 'cycles_publies': 6000.0}
    INVESTISSEMENT = {'ht': 120000.0, 'ttc': 144000.0, 'lignes': [
        {'designation': 'Onduleur(s) hybride(s)', 'ht': 20000.0, 'ttc': 24000.0, 'onduleur': True,
         'optionnelle': False},
        {'designation': 'Panneau', 'ht': 60000.0, 'ttc': 72000.0, 'optionnelle': False},
        {'designation': 'Batterie Dyness 10 kWh', 'ht': 40000.0, 'ttc': 48000.0, 'optionnelle': False}]}
    SCENARIOS = [{'cle': 'production', 'variation_pct': -30, 'source': 'P (test)'},
                 {'cle': 'degradation', 'variation_pct': 0.75, 'source': 'D (test)'},
                 {'cle': 'tarif_kwh', 'variation_pct': -10, 'source': 'T (test)'},
                 {'cle': 'indexation_tarif', 'variation_pct': 2, 'source': 'I (test)'}]

    def _valoriser(self):
        from apps.ventes import tarif_ci
        from apps.ventes.domain.etude_ci import _valoriseur
        return _valoriseur(tarif_ci.tarif_applicable(_TARIF_MT_DECLARE), _TARIF_MT_DECLARE, self.CHARGE, 'mt')

    def _reevaluer(self, valoriser, production=None):
        from apps.ventes.domain.sensibilites_option_avec import reevaluateur
        return reevaluateur(15.0, {'combinaison': []}, self.BANQUE, hybrides=[], charge=self.CHARGE,
                            production=lambda: production or self.PRODUCTION, tension='mt',
                            revente_choisie=False, valoriser=valoriser)

    def _bloc(self, reevaluer='moteur', valoriser=None, sensibilites='scenarios'):
        from apps.ventes.domain.etude_ci_batterie import _bloc
        valoriser = valoriser or self._valoriser()
        evaluation = self._reevaluer(valoriser)(1.0)
        ctx = {'taux_tva_pct': 20, 'batterie': self.BANQUE,
               'sensibilites': self.SCENARIOS if sensibilites == 'scenarios' else sensibilites,
               'reevaluer': self._reevaluer(valoriser) if reevaluer == 'moteur' else reevaluer}
        return evaluation, _bloc(evaluation, valoriser, ctx, investissement=self.INVESTISSEMENT)

    def test_niveau_14_quatre_scenarios_meme_forme_que_l_option_reseau(self):
        _evaluation, bloc = self._bloc()
        lignes = bloc['economie_flux']['sensibilites']
        self.assertEqual([(s['cle'], s['source']) for s in lignes],
                         [(s['cle'], s['source']) for s in self.SCENARIOS])
        for ligne in lignes:
            with self.subTest(cle=ligne['cle']):
                self.assertEqual(set(ligne), _CLES_LIGNE)
                self.assertGreater(ligne['retour_dixieme_ans'], ligne['retour_ans'] - 1)
                self.assertLessEqual(ligne['retour_dixieme_ans'], ligne['retour_ans'])
        # Une grandeur à la fois sur le flux central (remplacement de la batterie compris).
        central = bloc['economie_flux']['flux_ht']['flux'][-1]['cumul_mad']
        par_cle = {s['cle']: s for s in lignes}
        self.assertLess(par_cle['degradation']['cumul_25_ans_mad'], central)
        self.assertGreater(par_cle['indexation_tarif']['cumul_25_ans_mad'], central)
        self.assertLess(par_cle['tarif_kwh']['economie_annee1_mad'],
                        bloc['economie_ci']['economie_annee1']['total_mad'])

    def test_niveau_14_production_re_simulee_jamais_mise_a_l_echelle(self):
        """La batterie est re-simulée sur la production × 0,7 : son énergie
        restituée change et l'économie an 1 n'est PAS l'économie centrale × 0,7."""
        reevaluer = self._reevaluer(self._valoriser())
        central, scenario = reevaluer(1.0), reevaluer(0.7)
        self.assertNotEqual(scenario['bilan']['batterie']['restitue_kwh_an'],
                            central['bilan']['batterie']['restitue_kwh_an'])
        ligne = self._bloc()[1]['economie_flux']['sensibilites'][0]
        self.assertEqual(ligne['cle'], 'production')
        self.assertAlmostEqual(ligne['economie_annee1_mad'], scenario['economie'], places=2)
        self.assertGreater(abs(ligne['economie_annee1_mad'] - 0.7 * central['economie']), 100.0)
        self.assertLess(ligne['economie_annee1_mad'], central['economie'])

    def test_niveau_14_remplacement_suit_le_bilan_du_scenario(self):
        """Niveau 13 par scénario : l'année de remplacement de la batterie est
        lue sur les cycles par an du bilan DU scénario (moins de production ⇒
        moins de cycles ⇒ plus tard, ici au-delà de l'horizon)."""
        from apps.ventes.domain import etude_ci_batterie as m
        from apps.ventes.domain.sensibilites_option_avec import flux_du_scenario_production
        from apps.ventes.economie_ci_options import cycles_par_an_du_bilan
        valoriser = self._valoriser()
        reevaluer = self._reevaluer(valoriser)
        evaluation, bloc = self._bloc()

        def annees(flux):
            return [r['annee'] for r in flux['remplacements'] if r['composant'] == 'batterie']

        attendu = int(6000 // cycles_par_an_du_bilan(evaluation['bilan'])) + 1
        self.assertEqual(annees(bloc['economie_flux']), [attendu])
        flux, _eco = flux_du_scenario_production(
            self.SCENARIOS[0], reevaluer, complet=valoriser.complet,
            flux_de=lambda ev, e, _c: m._flux_option_avec(
                ev, e, self.INVESTISSEMENT, {'taux_tva_pct': 20, 'batterie': self.BANQUE}))
        annee = int(6000 // cycles_par_an_du_bilan(reevaluer(0.7)['bilan'])) + 1
        self.assertGreater(annee, attendu)
        self.assertEqual(annees(flux), [annee] if annee <= 25 else [])

    def test_niveau_14_scenario_non_chiffrable_motif_sans_chiffre(self):
        from apps.ventes.domain import sensibilites_option_avec as so

        def sans_chiffre(ligne, motif):
            self.assertEqual(ligne['motif'], motif)
            for cle in ('economie_annee1_mad', 'retour_ans', 'retour_dixieme_ans', 'tri_pct',
                        'cumul_25_ans_mad', 'ecart_retour_ans', 'ecart_tri_pct'):
                self.assertIsNone(ligne[cle], cle)

        sans_chiffre(self._bloc(reevaluer=None)[1]['economie_flux']['sensibilites'][0],
                     so.MOTIF_AVEC_NON_REPRODUCTIBLE)
        # Une ré-évaluation qui ne retrouve pas le central (étude périmée).
        valoriser = self._valoriser()
        autre = self._reevaluer(valoriser, production=[dict(p, production_kwh_kwc=[
            0.9 * v for v in p['production_kwh_kwc']]) for p in self.PRODUCTION])
        sans_chiffre(self._bloc(reevaluer=autre)[1]['economie_flux']['sensibilites'][0],
                     so.MOTIF_AVEC_NON_REPRODUCTIBLE)

        class SansTarif:
            """Un valoriseur sans le tarif de l'étude (``contexte``)."""
            def __init__(self, reel):
                self.reel, self.complet = reel, reel.complet

            def __call__(self, bilan):
                return self.reel(bilan)
        lignes = self._bloc(valoriser=SansTarif(valoriser))[1]['economie_flux']['sensibilites']
        sans_chiffre(lignes[2], so.MOTIF_AVEC_TARIF_ABSENT)
        self.assertNotIn('motif', lignes[1])
        self.assertNotIn('motif', lignes[0])

    def test_niveau_13_aucune_sensibilite_servie(self):
        from types import SimpleNamespace

        from apps.ventes.domain.sensibilites_option_avec import scenarios_du_devis
        self.assertIsNone(scenarios_du_devis(None, SimpleNamespace(regles_calcul=13)))
        self.assertEqual(scenarios_du_devis(None, SimpleNamespace(regles_calcul=14)), [])
        neuf = self._bloc()[1]['economie_flux']
        hier = self._bloc(sensibilites=None)[1]['economie_flux']
        self.assertNotIn('sensibilites', hier)
        self.assertEqual({k: v for k, v in neuf.items() if k != 'sensibilites'}, hier)

    def test_niveau_14_scenarios_atteignent_le_contexte_des_deux_chemins(self):
        """``sensibilites`` passé à ``option_avec_de_l_etude`` atteint le
        contexte du bloc (étude ET lignes), jamais le dimensionnement."""
        from apps.ventes.domain import etude_ci_batterie as m
        resultat = {'evaluation': {'kwc': 1, 'batterie': {'produit': 1, 'quantite': 2},
                                   'onduleurs': {'combinaison': ciq120.HYBRIDE_CABLABLE}},  # D-ACAL-103
                    'prix_a_renseigner': [], 'hypotheses': [], 'alertes': [], 'motif': None}
        catalogue = {'batterie': {'hybrides': [1], 'batteries': [{'produit': 1}]}}
        vus = []
        with mock.patch.object(m, 'batteries_compatibles', return_value=[1]), \
                mock.patch.object(m, '_dimensionner', return_value=resultat) as dim, \
                mock.patch.object(m, '_option_dominee', return_value=False), \
                mock.patch.object(m, 'verdict_rentabilite', return_value=None), \
                mock.patch.object(m, '_bloc', lambda ev, val, ctx, **k: vus.append(ctx) or {}), \
                mock.patch.object(m, '_option_imposee', lambda imp, ctx: vus.append(ctx) or {'k': 1}):
            for imposee in (None, {'x': 1}):
                m.option_avec_de_l_etude(catalogue, {'kwc': 1}, choix='avec', lead=None, imposee=imposee,
                                         tva_recuperable={'valeur': 'inconnu'}, production=[],
                                         sensibilites=self.SCENARIOS[:1])
        self.assertEqual([c['sensibilites'] for c in vus], [self.SCENARIOS[:1]] * 2)
        self.assertIsNotNone(vus[0]['reevaluer'])
        self.assertNotIn('sensibilites', dim.call_args.kwargs)

    def test_niveau_14_rangees_jusqu_a_l_argent_et_au_tableau(self):
        """``_argent_option_avec`` fusionne ``economie_flux`` : les lignes de
        l'option arrivent dans l'argent PUBLIC et dans le tableau de la page 3,
        nommées par ``_nom_scenario``, retour au dixième."""
        from functools import partial

        from apps.ventes.quote_engine.ci import blocs as ci_blocs
        from apps.ventes.quote_engine.ci.synthese import _argent_option_avec
        from apps.ventes.quote_engine.industriel.finance import _tableau_sensibilites
        from apps.ventes.quote_engine.residential.theme import fmt
        bloc = self._bloc()[1]
        argent, motif = _argent_option_avec(bloc, 'industriel')
        self.assertIsNone(motif)
        self.assertEqual(argent['sensibilites'], bloc['economie_flux']['sensibilites'])
        html = _tableau_sensibilites({}, argent, fmt, partial(ci_blocs.libelle, {}))
        production = bloc['economie_flux']['sensibilites'][0]
        self.assertIn('Production -30&#160;%', html)
        rangee = html[html.index('Production -30'):].split('</tr>')[0]
        self.assertIn(('%.1f' % production['retour_dixieme_ans']).replace('.', ','), rangee)


class SensibilitesNiveau14DevisTests(ciq120.OptionBatterieCITests):
    """Un devis automatique à deux options au niveau 14 sert les sensibilités
    des DEUX options, retours au dixième ; au niveau 13, l'option « avec » n'en
    sert aucune (jeux de ``OptionBatterieCITests``, sans rejouer ses tests)."""

    def test_niveau_14_deux_options_servent_leurs_sensibilites(self):
        from apps.ventes.domain.sensibilites_option_avec import _retenus
        devis = self._auto(self._boulangerie())
        attendues = [s['cle'] for s in _retenus(eco.reglages_economie_ci(self.co)['sensibilites_ci'])]
        self.assertTrue(attendues)
        for niveau in (14, 13):
            ciq120.Devis.objects.filter(pk=devis.pk).update(regles_calcul=niveau)
            devis.refresh_from_db()
            with mock.patch.object(ciq120.tarif_ci, 'tarif_applicable', side_effect=ciq120._tarif_grille):
                ciq120.etude_ci.rafraichir_etude_ci_devis(devis, force=True)
                devis.refresh_from_db()
                reseau = eco.economie_ci_pour_devis(devis, self.co)['sensibilites']
            flux = devis.etude_params['etude_ci']['option_avec']['economie_flux']
            self.assertIsNotNone(flux, niveau)
            if niveau == 13:
                self.assertNotIn('sensibilites', flux)
                continue
            for option, lignes in (('sans', reseau), ('avec', flux['sensibilites'])):
                self.assertEqual([s['cle'] for s in lignes], attendues, option)
                for ligne in lignes:
                    with self.subTest(option=option, cle=ligne['cle']):
                        if option == 'avec':   # re-simulée sur les entrées de l'option servie
                            self.assertNotIn('motif', ligne)
                        self.assertIn('retour_dixieme_ans', ligne)
                        self.assertEqual(ligne['retour_dixieme_ans'] is None, ligne['retour_ans'] is None)
                        if ligne['retour_ans'] is not None:
                            self.assertGreater(ligne['retour_dixieme_ans'], ligne['retour_ans'] - 1)
                            self.assertLessEqual(ligne['retour_dixieme_ans'], ligne['retour_ans'])


class DepartUneBatterieRemiseTests(ciq120.RecomposerBatteriesTests):
    """Fondateur 19/11/2026 (« apply the reduction if it exists to the one
    battery price ») — la remise globale du devis est DANS le prix à une
    batterie (jeux de ``RecomposerBatteriesTests``, sans rejouer ses tests)."""

    def _bloc(self, devis):
        etude = ciq120.Devis.objects.get(pk=devis.pk).etude_params['etude_ci']
        self.assertNotIn('depart_une_batterie_refus', etude, etude.get('depart_une_batterie_refus'))
        return etude['depart_une_batterie']

    def test_remise_globale_dans_le_prix_a_une_batterie(self):
        from decimal import Decimal

        from apps.ventes.utils.options import AVEC_BATTERIE, option_totaux
        devis, _reco = self._devis()
        self.assertEqual(self._cocher(devis).status_code, 200)
        plein = self._bloc(devis)
        self.assertNotIn('remise_comprise', plein)
        # Le vendeur pose 2 % de remise sur le devis, case déjà cochée : le
        # prochain rafraîchissement de l'étude (non forcé) recalcule le bloc.
        ciq120.Devis.objects.filter(pk=devis.pk).update(remise_globale=Decimal('2'))
        devis.refresh_from_db()
        with mock.patch.object(ciq120.tarif_ci, 'tarif_applicable', side_effect=ciq120._tarif_grille):
            ciq120.etude_ci.rafraichir_etude_ci_devis(devis)
        remise = self._bloc(devis)
        self.assertIs(remise['remise_comprise'], True)
        self.assertEqual(remise['nb_panneaux'], plein['nb_panneaux'])
        self.assertLess(remise['total_ht'], plein['total_ht'])
        # 2 % de moins, à l'arrondi commercial près (palier de 100 MAD TTC).
        self.assertAlmostEqual(remise['total_ht'], plein['total_ht'] * 0.98, delta=200)
        # Exactitude : le vrai geste « Batteries au départ » = 1 donne ce prix,
        # et la remise du devis est toujours là.
        self.assertEqual(self._post(devis.pk, 1).status_code, 200)
        apres = ciq120.Devis.objects.get(pk=devis.pk)
        self.assertEqual(apres.remise_globale, Decimal('2'))
        totaux = option_totaux(apres, AVEC_BATTERIE)
        self.assertEqual(Decimal(str(remise['total_ttc'])), totaux['ttc'])
        self.assertEqual(Decimal(str(remise['total_ht'])), totaux['ht'])


class DevisFinalEnregistreTests(ciq120.RecomposerBatteriesTests):
    """Fondateur 19/11/2026 (« where is final quote button ») — la case
    « Devis final » s'enregistre par le PATCH fusionnant ``etude-params`` et
    tout rendu du devis la suit (jeux de ``RecomposerBatteriesTests``)."""

    def _patch(self, devis, valeur):
        from rest_framework.test import APIClient
        api = APIClient()
        api.force_authenticate(self.user)
        url = '/api/django/ventes/devis/%s/etude-params/' % devis.pk
        return api.patch(url, {'devis_final': valeur}, format='json')

    def test_la_case_s_enregistre_et_le_document_suit(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        devis, _reco = self._devis()
        self.assertFalse(build_quote_data(devis, {})['devis_final'])
        # T4-X6-004 (D-CIQ-5) — la case dit « visite faite » : la boulangerie
        # du jeu (puissance souscrite et type de surface non déclarés) exige
        # la visite avant le devis ; sans elle la case est refusée (409, garde
        # ``devis_pdf.refus_devis_final``, couverte par
        # ``test_apdf_options_relayees``). La visite est donc enregistrée.
        self.assertEqual(self._patch(devis, True).status_code, 409)
        ciq120.Lead.objects.filter(pk=devis.lead_id).update(visite_effectuee=True)
        etude_avant = dict(
            ciq120.Devis.objects.get(pk=devis.pk).etude_params)
        self.assertEqual(self._patch(devis, True).status_code, 200)
        apres = ciq120.Devis.objects.get(pk=devis.pk)
        self.assertIs(apres.etude_params['devis_final'], True)
        # Rien d'autre ne bouge : ni l'étude, ni les options de l'écran.
        reste = {k: v for k, v in apres.etude_params.items()
                 if k != 'devis_final'}
        self.assertEqual(reste, etude_avant)
        data = build_quote_data(apres, {})
        self.assertTrue(data['devis_final'])
        # Décochée (null) : la clé est retirée, le document d'hier revient.
        self.assertEqual(self._patch(devis, None).status_code, 200)
        retire = ciq120.Devis.objects.get(pk=devis.pk)
        self.assertNotIn('devis_final', retire.etude_params)
        self.assertFalse(build_quote_data(retire, {})['devis_final'])

    def test_une_valeur_non_booleenne_est_refusee(self):
        devis, _reco = self._devis()
        self.assertEqual(self._patch(devis, 'oui').status_code, 400)
        self.assertNotIn(
            'devis_final', ciq120.Devis.objects.get(pk=devis.pk).etude_params)


def _sans_tests_herites(classe):
    """Ces classes n'héritent que des JEUX DE DONNÉES : les tests du parent ne
    sont pas rejoués ici."""
    for parent in classe.__mro__[1:]:
        for nom in vars(parent):
            if nom.startswith('test_') and nom not in vars(classe):
                setattr(classe, nom, None)


_sans_tests_herites(RemplacementCyclesNiveau13FluxTests)
_sans_tests_herites(RemplacementCyclesNiveau13DevisTests)
_sans_tests_herites(SensibilitesNiveau14DevisTests)
_sans_tests_herites(DepartUneBatterieRemiseTests)
_sans_tests_herites(DevisFinalEnregistreTests)


class ContratDixiemeEtLibellePosteTests(SimpleTestCase):
    """ACAL1223 — le contrat ``economie_ci.json`` porte, posées SEULES (PACT10)
    pour ACAL1224/ACAL1225 (serveur) et ACAL1213/ACAL1214 (écran),
    ``indicateurs.retour_dixieme_ans`` de l'offre réseau et ``libelle`` sur
    chaque poste ; les clés d'hier restent là (ajout seulement)."""

    def _contrat(self):
        import json
        from pathlib import Path
        chemin = Path(__file__).resolve().parent.parent / 'contract_samples' / 'economie_ci.json'
        return json.loads(chemin.read_text(encoding='utf-8'))

    def test_l_offre_reseau_porte_son_retour_au_dixieme_derive_du_flux_servi(self):
        from apps.ventes.economie_ci_options import retour_au_dixieme
        doc = self._contrat()
        ex = doc['exemple_industriel_mt']
        ind = ex['indicateurs']
        self.assertEqual(ex['base'], 'ht')
        # Le nombre de l'exemple est DÉRIVÉ : la fonction du PDF sur le flux principal.
        self.assertEqual(ind['retour_dixieme_ans'], retour_au_dixieme(ex['flux_ht']))
        self.assertEqual(ind['retour_dixieme_ans'], round(ind['retour_dixieme_ans'], 1))
        self.assertGreater(ind['retour_dixieme_ans'], ind['retour_ans'] - 1)
        self.assertLessEqual(ind['retour_dixieme_ans'], ind['retour_ans'])
        self.assertIn('retour_dixieme_ans', doc['regles_sortie']['indicateurs'])

    def test_chaque_poste_porte_un_libelle_de_metier(self):
        doc = self._contrat()
        ex = doc['exemple']
        postes = (ex['economie_annee1']['par_poste'] + ex['facture_avant']['energie_par_poste']
                  + ex['facture_apres']['energie_par_poste'])
        self.assertTrue(postes)
        for p in postes:
            with self.subTest(poste=p['poste']):
                self.assertIsInstance(p['libelle'], str)
                self.assertTrue(p['libelle'].strip())
                self.assertNotEqual(p['libelle'], p['poste'])
                self.assertNotIn('D-CIQ', p['libelle'])
                self.assertNotIn('_', p['libelle'])
        self.assertEqual([p['poste'] for p in ex['economie_annee1']['par_poste']], ['tranche_2'])
        for cle in ('economie_annee1', 'facture_avant / facture_apres'):
            self.assertIn('libelle', doc['regles_sortie'][cle])


def _etude_industrielle_realiste():
    """Le devis industriel de l'empreinte de conception (``golden/conception/ci_industriel.json``,
    ~115 kWc, 18 lignes, total HT 416 833,33) : son étude C&I stockée COMPLÈTE (matrice
    horaire du moteur), ses lignes CLIENT (onduleurs comptés) et ses totaux."""
    import json
    from pathlib import Path
    golden = json.loads((Path(__file__).resolve().parent / 'golden' / 'conception'
                         / 'ci_industriel.json').read_text(encoding='utf-8'))
    lignes = []
    for li in golden['lignes']:
        if li.get('type_ligne', 'produit') != 'produit':
            continue
        ht = float(li['quantite']) * float(li['prix_unitaire']) * (1 - float(li['remise'] or 0) / 100)
        lignes.append({'designation': li['designation'], 'ht': ht,
                       'ttc': ht * (1 + float(li['taux_tva']) / 100),
                       'optionnelle': li['optionnelle'],
                       'onduleur': str(li.get('role_devis') or '').startswith('onduleur'),
                       'panneau': li.get('role_devis') == 'panneau', 'role_ci': None})
    champs = golden['champs_devis']
    return (golden['etude_params']['etude_ci'], lignes,
            {'ht': float(champs['total_ht']), 'ttc': float(champs['total_ttc'])})


class OffreReseauRetourDixiemeTests(SimpleTestCase):
    """ACAL1224 — ``assembler_economie_ci`` sert ``indicateurs.retour_dixieme_ans`` de
    l'offre réseau : le retour que le PDF imprime (``quote_engine.ci.couverture.retour_dixieme``
    sur le bloc servi), en lecture comme en aperçu ; ``retour_ans`` (entier) inchangé ; un
    devis aux règles d'avant le niveau 3 garde l'entier que son PDF imprime. Étude COMPLÈTE
    d'un vrai devis industriel, dans les trois bases."""

    def _bloc(self, tva, **reglages):
        import copy
        etude, lignes, investissement = _etude_industrielle_realiste()
        return eco.assembler_economie_ci(
            copy.deepcopy(etude), tarif_declare={'contrat': 'bt_patente'},
            saisies={'tva_recuperable': {'valeur': tva, 'provenance': 'declare_client',
                                         'saisi_le': '2026-11-20'}},
            investissement=investissement, lignes=lignes,
            mode_installation='industriel', reglages=reglages)

    def _imprime(self, bloc, regles_origine=False):
        """Le retour que le PDF imprime, sous les drapeaux de règles du rendu."""
        import contextvars
        from apps.ventes.quote_engine.ci import couverture
        from apps.ventes.quote_engine.montants import poser_regles_origine

        def rendu():
            poser_regles_origine(False, avant_2710=regles_origine)
            argent = eco.economie_ci_publique(bloc)
            return couverture.retour_dixieme(argent, argent['indicateurs']['retour_ans'])
        return contextvars.copy_context().run(rendu)

    def test_offre_reseau_dixieme_egal_au_pdf_dans_les_trois_bases(self):
        from apps.ventes.economie_ci_options import retour_au_dixieme
        for tva, base, cle in (('oui', 'ht', 'flux_ht'), ('non', 'ttc', 'flux_ttc'),
                               ('inconnu', 'deux', 'flux_ht')):
            with self.subTest(tva=tva):
                bloc = self._bloc(tva)
                self.assertEqual(bloc['base'], base)
                ind = bloc['indicateurs']
                self.assertEqual(ind['retour_ans'], bloc[cle]['retour_ans'])
                self.assertIsInstance(ind['retour_ans'], int)
                self.assertIn('retour_dixieme_ans', ind)
                self.assertEqual(ind['retour_dixieme_ans'], self._imprime(bloc))
                self.assertEqual(ind['retour_dixieme_ans'], retour_au_dixieme(bloc[cle]))
                # Cumul de l'an 3 à peine négatif sur ce devis : 3,0 (arrondi) pour un entier 4.
                self.assertGreaterEqual(ind['retour_dixieme_ans'], ind['retour_ans'] - 1)
                self.assertLessEqual(ind['retour_dixieme_ans'], ind['retour_ans'])
                # Même valeur dans la charge utile client (écran, PDF, /proposition).
                self.assertEqual(eco.economie_ci_publique(bloc)['indicateurs']['retour_dixieme_ans'],
                                 ind['retour_dixieme_ans'])

    def test_devis_envoye_avant_le_niveau_3_garde_l_entier_imprime(self):
        bloc = self._bloc('oui', regles_origine=True)
        ind = bloc['indicateurs']
        self.assertEqual(ind['retour_dixieme_ans'], ind['retour_ans'])
        self.assertEqual(ind['retour_dixieme_ans'], self._imprime(bloc, regles_origine=True))

    def test_investissement_non_chiffre_aucun_dixieme_invente(self):
        import copy
        etude, lignes, _inv = _etude_industrielle_realiste()
        bloc = eco.assembler_economie_ci(
            copy.deepcopy(etude), tarif_declare={'contrat': 'bt_patente'},
            investissement={'ht': None, 'ttc': None}, lignes=lignes,
            mode_installation='industriel')
        ind = bloc['indicateurs'] or {}
        self.assertIsNone(ind.get('retour_ans'))
        self.assertIsNone(ind.get('retour_dixieme_ans'))
