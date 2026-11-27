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


# ── ADEV81 — investissement incomplet (D-ACI-8=a) ───────────────────────────

def _assembler(investissement, lignes=None, *, controle_lignes=False,
               apercu=None):
    from apps.ventes.tests.test_ciq210_branchement import _apercu
    return eco.assembler_economie_ci(
        apercu if apercu is not None else _apercu('mt'),
        investissement=investissement, lignes=lignes,
        mode_installation='industriel', controle_lignes=controle_lignes)


def _ligne(designation, ht, *, panneau=False, onduleur=False):
    return {'designation': designation, 'ht': ht, 'ttc': round(ht * 1.2, 2),
            'optionnelle': False, 'onduleur': onduleur, 'panneau': panneau,
            'role_ci': None}


def _omission_investissement(bloc):
    return next((o for o in bloc['omissions']
                 if o['cle'] == 'investissement_mad'), None)


class InvestissementNonChiffreTest(SimpleTestCase):
    """ADEV81 — jamais « retour 0 an » ni « TRI 895 % » sur un investissement
    nul ou partiel : flux vides, indicateurs nuls, omission nommée ;
    l'économie de l'année 1, elle, reste servie."""

    def _assert_non_chiffre(self, bloc):
        self.assertEqual(bloc['statut'], 'calcule')
        omis = _omission_investissement(bloc)
        self.assertIsNotNone(omis)
        # AMOT85 — « non encore chiffré » (article sans prix) ou « à compléter
        # après la visite technique » (postes hors total seulement).
        self.assertTrue(omis['motif'].startswith((
            'investissement non encore chiffré',
            'investissement à compléter après la visite technique')),
            omis['motif'])
        for cle in ('flux_ht', 'flux_ttc'):
            if bloc[cle] is not None:
                self.assertEqual(bloc[cle]['flux'], [])
                self.assertIsNone(bloc[cle]['retour_ans'])
        ind = bloc['indicateurs']
        self.assertIsNone(ind['retour_ans'])
        self.assertIsNone(ind['tri_pct'])
        self.assertIsNone(ind['lcoe_mad_kwh'])
        self.assertEqual(bloc['jalons'], [])
        self.assertGreater(bloc['economie_annee1']['total_mad'], 0)

    def test_montant_refuse_zero_pour_l_investissement(self):
        self.assertIsNone(eco._montant(0, strictement_positif=True))
        self.assertIsNone(eco._montant('0.00', strictement_positif=True))
        self.assertEqual(eco._montant(0), 0.0)
        res = eco.base_economique('oui', investissement={'ht': 0, 'ttc': 0})
        self.assertIsNone(res['investissement_ht_mad'])
        self.assertIsNone(res['base_amortissable_mad'])

    def test_investissement_nul_aucun_flux_omission_posee(self):
        bloc = _assembler({'ht': 0.0, 'ttc': 0.0})
        self._assert_non_chiffre(bloc)
        self.assertEqual(_omission_investissement(bloc)['motif'],
                         'investissement non encore chiffré (3 articles '
                         'sans prix)')

    def test_mille_mad_sur_deux_lignes_sans_panneau_idem(self):
        lignes = [_ligne('Onduleur réseau Huawei 50kW Triphasé', 800.0,
                         onduleur=True),
                  _ligne('Smart Meter', 200.0)]
        bloc = _assembler({'ht': 1000.0, 'ttc': 1200.0}, lignes,
                          controle_lignes=True)
        self._assert_non_chiffre(bloc)

    def test_sans_controle_des_lignes_le_meme_devis_est_chiffre(self):
        """Test-du-test : le contrôle des lignes est ce qui retient le
        « retour 1 an » de 1 000 MAD (sinon il est imprimé)."""
        lignes = [_ligne('Smart Meter', 1000.0)]
        bloc = _assembler({'ht': 1000.0, 'ttc': 1200.0}, lignes)
        self.assertIsNone(_omission_investissement(bloc))
        self.assertIsNotNone(bloc['indicateurs']['retour_ans'])

    def test_article_de_taille_a_renseigner_absent_du_devis(self):
        from apps.ventes.tests.test_ciq210_branchement import _apercu
        apercu = _apercu('mt')
        composition = apercu['composition']
        composition['lignes'].insert(0, {
            'role': 'panneau', 'produit': 7, 'designation': 'Module 580 Wc',
            'quantite': 91, 'unite': 'u', 'prix_connu': False,
            'motif': 'prix à renseigner', 'a_confirmer_visite': False})
        composition['prix_a_renseigner'].insert(0, 'Module 580 Wc')
        lignes = [_ligne('Panneau 550W générique', 400000.0, panneau=True),
                  _ligne('Onduleur réseau Huawei 50kW Triphasé', 60000.0,
                         onduleur=True)]
        bloc = _assembler({'ht': 460000.0, 'ttc': 552000.0}, lignes,
                          controle_lignes=True, apercu=apercu)
        self._assert_non_chiffre(bloc)
        self.assertEqual(_omission_investissement(bloc)['motif'],
                         'investissement non encore chiffré (4 articles '
                         'sans prix)')

    def test_article_de_taille_a_chiffrer_apres_visite(self):
        from apps.ventes.tests.test_ciq210_branchement import _apercu
        apercu = _apercu('mt')
        composition = apercu['composition']
        composition['prix_a_renseigner'] = []
        composition['a_chiffrer_visite'] = [
            'Onduleur réseau Huawei 50kW Triphasé']
        lignes = [_ligne('Panneau 550W', 400000.0, panneau=True)]
        bloc = _assembler({'ht': 400000.0, 'ttc': 480000.0}, lignes,
                          controle_lignes=True, apercu=apercu)
        self._assert_non_chiffre(bloc)
        # AMOT85 — seul un poste HORS TOTAL manque : le motif dit la visite,
        # jamais « sans prix » à côté d'un investissement imprimé.
        self.assertEqual(_omission_investissement(bloc)['motif'],
                         'investissement à compléter après la visite '
                         'technique (1 poste hors total)')

    def test_investissement_complet_toujours_chiffre(self):
        # D-ACI-2 (a) : « complet » = aucun article de la composition laissé
        # hors devis (ni « prix à renseigner », ni « à chiffrer après visite »).
        from apps.ventes.tests.test_ciq210_branchement import _apercu
        apercu = _apercu('mt')
        apercu['composition']['prix_a_renseigner'] = []
        apercu['composition']['a_chiffrer_visite'] = []
        lignes = [_ligne('Panneau 550W', 700000.0, panneau=True),
                  _ligne('Onduleur réseau Huawei 50kW Triphasé', 200000.0,
                         onduleur=True)]
        bloc = _assembler({'ht': 900000.0, 'ttc': 1080000.0}, lignes,
                          controle_lignes=True, apercu=apercu)
        self.assertIsNone(_omission_investissement(bloc))
        self.assertIsNotNone(bloc['indicateurs']['retour_ans'])
        self.assertTrue(bloc['flux_ht']['flux'])


def _textes(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for v in o.values():
            yield from _textes(v)
    elif isinstance(o, list):
        for v in o:
            yield from _textes(v)


class AucunCodeDeDecisionServiTest(SimpleTestCase):
    """ACAL1225 — l'économie C&I ne sert aucun code de décision (« D-CIQ-n »)
    à l'écran, et chaque poste porte son libellé de métier ; ``poste`` et
    ``motif`` gardent leur forme. Études complètes : le devis industriel de
    l'empreinte de conception (BT, tranches) et l'aperçu MT du contrat."""

    def _blocs(self):
        import copy
        from apps.ventes.tests.test_ciq206_flux_ci import _etude_industrielle_realiste
        from apps.ventes.tests.test_ciq210_branchement import _apercu
        etude, lignes, investissement = _etude_industrielle_realiste()
        for tva in ('oui', 'non', 'inconnu'):
            saisies = {'tva_recuperable': {'valeur': tva, 'provenance': 'declare_client',
                                           'saisi_le': '2026-11-20'},
                       'parcours_aide': 'sr500'}
            yield tva, 'bt', eco.assembler_economie_ci(
                copy.deepcopy(etude), tarif_declare={'contrat': 'bt_patente'},
                saisies=saisies, investissement=investissement, lignes=lignes,
                mode_installation='industriel')
            yield tva, 'mt', eco.assembler_economie_ci(
                _apercu('mt'), saisies=saisies,
                investissement={'ht': 900000.0, 'ttc': 1080000.0},
                mode_installation='industriel')

    def test_aucun_texte_servi_ne_porte_de_code(self):
        for tva, tension, bloc in self._blocs():
            for texte in _textes(bloc):
                # Seule exception : la source de l'horizon, CLÉ du PDF
                # (``couverture.SOURCES_CLIENT`` → ``ci_src_horizon``) — à changer
                # là d'abord ; le PDF l'imprime déjà sans le code.
                if texte == eco.HORIZON_CI_SOURCE:
                    continue
                with self.subTest(tva=tva, tension=tension, texte=texte):
                    self.assertNotIn('D-CIQ', texte)

    def test_constantes_sans_code(self):
        from apps.ventes.domain import etude_ci
        for texte in (eco.MOTIF_BASE_HT, eco.MOTIF_BASE_TTC, eco.MOTIF_BASE_DEUX,
                      eco.MOTIF_FINANCEMENT_ABSENT, eco.MOTIF_SR500, etude_ci.METHODE,
                      etude_ci.METHODE_8760, etude_ci.SOURCE_REGIME):
            with self.subTest(texte=texte):
                self.assertNotIn('D-CIQ', texte)

    def test_chaque_poste_porte_son_libelle(self):
        vus = set()
        for tva, tension, bloc in self._blocs():
            postes = list(bloc['economie_annee1']['par_poste'])
            for cle in ('facture_avant', 'facture_apres'):
                postes += (bloc[cle] or {}).get('energie_par_poste') or []
            self.assertTrue(postes, tension)
            for p in postes:
                with self.subTest(tva=tva, tension=tension, poste=p['poste']):
                    libelle = p.get('libelle')
                    self.assertTrue(libelle)
                    self.assertNotEqual(libelle, p['poste'])
                    self.assertNotIn('_', libelle)
                    self.assertNotIn('D-CIQ', libelle)
                    vus.add((p['poste'], libelle))
        self.assertIn(('pointe', 'Énergie heures de pointe'), vus)
        self.assertTrue(any('+' in poste and libelle == 'Énergie, toutes tranches'
                            for poste, libelle in vus), vus)
        self.assertTrue(any(poste.startswith('tranche_') and libelle == 'Énergie tranche '
                            + poste.split('_')[1] for poste, libelle in vus), vus)
