"""AGR125 — le calepinage pompage et le devis publient les MÊMES 12 volumes.

Parité SANS MOCK : la même société, le même catalogue, la même ville (Agadir,
table PVGIS vendorisée — aucun appel réseau, aucune coordonnée), la même HMT
et le même kWc ⇒ ``POST /calepinage/calepinages/<pk>/pompage/`` rend dans
``volumes.m3_mois_pvgis`` exactement la production de
``POST /ventes/etude-pompage/preview/`` (``production.m3_jour_mois`` × jours).
La forme de la réponse calepinage reste celle de son contrat.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.calepinage.tests.test_agr125_parite_devis"
"""
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.calepinage.models import Calepinage
from apps.calepinage.services.pompage import JOURS_PAR_MOIS, hmt_du_puits
from apps.crm.models import Lead
from apps.parametres.models import CompanyProfile
from apps.roles.models import Role
from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
from apps.stock.models import Categorie, FicheTechnique, Produit
from apps.ventes.domain.pompage import etudier_pompage
from authentication.models import Company
from core.pompage.hydraulique import hmt_composantes

User = get_user_model()

RACINE = Path(__file__).resolve().parents[2]
CONTRAT_CALEPINAGE = json.loads(
    (RACINE / 'calepinage' / 'contract_samples' / 'calepinage_pompage.json')
    .read_text(encoding='utf-8'))
CONTRAT_PREVIEW = json.loads(
    (RACINE / 'ventes' / 'contract_samples' / 'etude_pompage_preview.json')
    .read_text(encoding='utf-8'))

COURBE = {'debits_m3h': [0, 12, 24, 30, 36, 39],
          'hmt_m': [91, 85, 70, 60, 43, 34]}


class PariteVolumesDevisCalepinageTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.co = Company.objects.create(nom='AGR125 Co', slug='agr125-co')
        profil, _ = CompanyProfile.objects.get_or_create(company=cls.co)
        CompanyProfile.objects.filter(pk=profil.pk).update(
            agricole_pump_hours=Decimal('7'))
        cat_pompe = Categorie.objects.create(
            company=cls.co, nom='Pompes', type_equipement='pompe')
        cat_variateur = Categorie.objects.create(
            company=cls.co, nom='Variateurs', type_equipement='variateur')
        cls.pompe = Produit.objects.create(
            company=cls.co, nom='Pompe immergée OSP 30/8 — 7.5 kW 380V',
            categorie=cat_pompe, role_pompage='pompe', type_pompe='immergee',
            alimentation='tri', pompe_kw=Decimal('7.5'), tension_v=380,
            courbe_pompe=COURBE, prix_vente=Decimal('1000'),
            prix_achat=Decimal('600'))
        cls.variateur = Produit.objects.create(
            company=cls.co, nom='VARIATEUR VEICHI SI23 7.5KW 380V',
            categorie=cat_variateur, role_pompage='variateur_pompage',
            alimentation='tri', pompe_kw=Decimal('7.5'), tension_v=380,
            prix_vente=Decimal('1000'), prix_achat=Decimal('600'))
        FicheTechnique.objects.create(
            company=cls.co, produit=cls.variateur,
            type_fiche='variateur_pompage', ond_mppt_v_min=Decimal('250'),
            ond_mppt_v_max=Decimal('750'), ond_v_max_abs=Decimal('800'),
            ond_i_max_mppt_a=Decimal('20'), ond_phases=3,
            var_v_sortie_v=Decimal('380'))
        cls.panneau = Produit.objects.create(
            company=cls.co, nom='Panneau 710W', prix_vente=Decimal('1000'),
            prix_achat=Decimal('600'))
        FicheTechnique.objects.create(
            company=cls.co, produit=cls.panneau, type_fiche='module',
            pmax_wc=Decimal('710'), vmp_v=Decimal('40'), voc_v=Decimal('48'),
            isc_a=Decimal('18'), imp_a=Decimal('17'))
        Produit.objects.create(
            company=cls.co, nom='Structure au sol pompage',
            role_pompage='structure_sol', prix_vente=Decimal('1000'),
            prix_achat=Decimal('600'))
        role = Role.objects.create(company=cls.co, nom='Directeur',
                                   permissions=list(DIRECTEUR_PERMISSIONS))
        cls.user = User.objects.create_user(
            username='agr125_user', password='x', company=cls.co, role=role)
        cls.lead = Lead.objects.create(company=cls.co, nom='Ferme Agadir',
                                       ville='Agadir')
        cls.calepinage = Calepinage.objects.create(
            company=cls.co, lead_id=cls.lead.pk, titre='Forage Agadir',
            statut=Calepinage.Statut.BROUILLON)

    def setUp(self):
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _preview(self):
        corps = json.loads(json.dumps(CONTRAT_PREVIEW['corps']))
        corps['localisation'] = {'ville': 'Agadir', 'lat': None, 'lon': None}
        return etudier_pompage(self.co, corps)

    def _calepinage(self, corps):
        rep = self.api.post(
            f'/api/django/calepinage/calepinages/{self.calepinage.pk}/pompage/',
            corps, format='json')
        self.assertEqual(rep.status_code, 200, rep.content[:500])
        return rep.json()

    def test_memes_douze_volumes_que_le_devis(self):
        devis = self._preview()
        production = devis['production']
        self.assertIsNotNone(production, devis.get('alertes'))
        self.assertEqual(production['mode'], 'courbe')
        self.assertEqual(production['source_irradiation'], 'pvgis')
        kwc = devis['champ']['kwc']
        hmt_m = devis['hmt']['valeur_m']
        self.assertIsNotNone(kwc, devis['champ'])
        self.assertIsNotNone(hmt_m)

        donnees = self._calepinage({'hmt_saisie': hmt_m, 'debit_souhaite_m3h': 1,
                                    'kwc': kwc})
        self.assertEqual(donnees['pompe']['produit'], self.pompe.pk)
        attendu = [round(production['m3_jour_mois'][i] * JOURS_PAR_MOIS[i], 1)
                   for i in range(12)]
        self.assertEqual(donnees['volumes']['m3_mois_pvgis'], attendu)
        self.assertTrue(donnees['volumes']['source_irradiation'].startswith('pvgis'))
        # le calcul plat reste publié à côté
        self.assertEqual(len(donnees['volumes']['m3_mois_plat']), 12)

    def test_forme_du_contrat_calepinage(self):
        devis = self._preview()
        donnees = self._calepinage({'hmt_saisie': devis['hmt']['valeur_m'],
                                    'debit_souhaite_m3h': 1,
                                    'kwc': devis['champ']['kwc']})
        exemple = CONTRAT_CALEPINAGE['exemple']
        self.assertEqual(set(donnees), set(exemple))
        self.assertEqual(set(donnees['hmt']), set(exemple['hmt']))
        self.assertEqual(set(donnees['volumes']), set(exemple['volumes']))
        self.assertEqual(set(donnees['entrees']), set(exemple['entrees']))
        texte = json.dumps(donnees)
        self.assertNotIn('prix_achat', texte)
        self.assertNotIn('marge', texte)

    def test_acal1267_pompes_a_courbe_sans_prix_les_deux_phrases_ne_se_contredisent_pas(self):
        """Seules des pompes à courbe SANS prix délivrent : le premier avertissement dit « chiffrée »
        (ces pompes délivrent, mais ne sont pas proposables) ; sans pompe sans prix, le texte d'avant reste."""
        Produit.objects.filter(pk=self.pompe.pk).update(prix_vente=Decimal('0'))
        donnees = self._calepinage({'hmt_saisie': 60, 'debit_souhaite_m3h': 12})
        self.assertIsNone(donnees['pompe'])
        premier, second = donnees['avertissements'][:2]
        self.assertTrue(premier.startswith(
            'aucune pompe à courbe chiffrée ne délivre le débit demandé à cette HMT'), premier)
        self.assertIn('des pompes conviennent mais n’ont pas de prix renseigné', second)

        Produit.objects.filter(pk=self.pompe.pk).update(prix_vente=Decimal('1000'))
        donnees = self._calepinage({'hmt_saisie': 60, 'debit_souhaite_m3h': 500})
        self.assertEqual([a for a in donnees['avertissements'] if 'ne délivre' in a],
                         ['aucune pompe à courbe ne délivre le débit demandé à cette HMT — aucun m³/jour '
                          'n’est publié (une pompe sans courbe ne produit jamais de volume chiffré)'])

    def test_sans_kwc_ni_variante_retenue_aucun_volume_physique(self):
        devis = self._preview()
        donnees = self._calepinage({'hmt_saisie': devis['hmt']['valeur_m'],
                                    'debit_souhaite_m3h': 1})
        self.assertIsNone(donnees['volumes']['m3_mois_pvgis'])
        self.assertIsNotNone(donnees['volumes']['m3_mois_plat'])

    def test_corps_hors_schema_refuse_400(self):
        """api-fuzz : un choix texte qui n'est pas une chaîne (``0``) est un
        400 qui nomme le champ — jamais « immergé » par défaut en silence ;
        les nombres ``null`` restent acceptés (= non renseignés)."""
        url = f'/api/django/calepinage/calepinages/{self.calepinage.pk}/pompage/'
        for champ in ('type_pompe', 'alim', 'materiau_conduite'):
            rep = self.api.post(url, {'hmt_saisie': None, champ: 0},
                                format='json')
            self.assertEqual(rep.status_code, 400, rep.content[:300])
            self.assertIn(champ, rep.json(), champ)
        rep = self.api.post(url, {'heures_pompage': 'beaucoup'}, format='json')
        self.assertEqual(rep.status_code, 400, rep.content[:300])
        donnees = self._calepinage({
            'hmt_saisie': None, 'debit_souhaite_m3h': None,
            'heures_pompage': None, 'volume_reservoir_m3': None})
        self.assertEqual(donnees['entrees']['heures_pompage'], 7.0)

    PUITS = {'debit_souhaite_m3h': 1, 'coefficient_rabattement_m_par_m3h': 0.25,
             'hauteur_refoulement_m': 4, 'longueur_tuyauterie_m': 350,
             'diametre_interieur_mm': 100, 'materiau_conduite': 'pehd',
             'pertes_singulieres_m': 0.8, 'pression_service_bar': 1.0}

    def test_acal806_hmt_et_volumes_suivent_le_niveau_de_chaque_mois(self):
        kwc = self._preview()['champ']['kwc']
        saison = self._calepinage(dict(
            self.PUITS, kwc=kwc, niveau_statique_ete_m=45,
            niveau_statique_hiver_m=35, mois_niveau_bas=[6, 7, 8, 9]))
        hiver = self._calepinage(dict(self.PUITS, kwc=kwc, niveau_statique_m=35))
        mensuelle = saison['hmt_mensuelle']
        self.assertEqual(mensuelle['manquantes'], [])
        ete_hmt = hmt_du_puits(**dict(
            {k: v for k, v in self.PUITS.items() if k != 'debit_souhaite_m3h'},
            debit_m3h=1, niveau_statique_m=45))['hmt_m']
        self.assertEqual(mensuelle['valeurs_m'][6], ete_hmt)
        self.assertEqual(mensuelle['valeurs_m'][0], hiver['hmt']['hmt_m'])
        self.assertEqual(saison['hmt']['hmt_m'], max(mensuelle['valeurs_m']))
        self.assertEqual(saison['entrees']['mois_niveau_bas'], [6, 7, 8, 9])
        juillet, janvier = 6, 0
        pvgis_saison = saison['volumes']['m3_mois_pvgis']
        pvgis_hiver = hiver['volumes']['m3_mois_pvgis']
        self.assertLess(pvgis_saison[juillet], pvgis_hiver[juillet])
        self.assertEqual(pvgis_saison[janvier], pvgis_hiver[janvier])
        self.assertIsNone(hiver['hmt_mensuelle'])

    def test_acal806_niveau_d_ete_sans_mois_erreur_nommee(self):
        donnees = self._calepinage(dict(self.PUITS, niveau_statique_ete_m=45))
        self.assertIn('mois_niveau_bas', donnees['erreurs'])
        self.assertIsNone(donnees['hmt_mensuelle'])

    def test_acal810_chaines_du_champ_contre_le_variateur(self):
        Calepinage.objects.filter(pk=self.calepinage.pk).update(
            resultat={'entree_electrique': {'module_produit': self.panneau.pk}})
        base = {'hmt_saisie': self._preview()['hmt']['valeur_m'],
                'debit_souhaite_m3h': 1}
        sonde = self._calepinage(dict(base, modules_en_serie=1))['chaines_variateur']
        longueur_max = sonde['fenetre']['longueur_max']
        self.assertGreater(longueur_max, 1)
        bloc = self._calepinage(dict(base, modules_en_serie=longueur_max))
        self.assertEqual(bloc['chaines_variateur']['verdict'], 'conforme')
        trop = self._calepinage(dict(base, modules_en_serie=longueur_max + 1))
        self.assertEqual(trop['chaines_variateur']['verdict'], 'hors_fenetre')
        longue = self._calepinage(dict(base, modules_en_serie=21))['chaines_variateur']
        self.assertEqual(longue['verdict'], 'hors_fenetre')
        self.assertEqual(longue['fenetre']['longueur_max'], longueur_max)
        sans = self._calepinage(base)['chaines_variateur']
        self.assertEqual(sans['verdict'], 'non_verifiable')
        self.assertEqual(sans['motif'], 'nombre de modules par chaîne non saisi')
        self.assertEqual(sans['champ'], 'modules_en_serie')

    def test_acal810_module_non_designe_non_verifiable(self):
        donnees = self._calepinage({'hmt_saisie': self._preview()['hmt']['valeur_m'],
                                    'debit_souhaite_m3h': 1, 'modules_en_serie': 12})
        bloc = donnees['chaines_variateur']
        self.assertEqual(bloc['verdict'], 'non_verifiable')
        self.assertIn('module PV non désigné', bloc['motif'])
        self.assertEqual(set(bloc), set(CONTRAT_CALEPINAGE['exemple']['chaines_variateur']))

    def _complet(self):
        devis = self._preview()
        return {'hmt_saisie': devis['hmt']['valeur_m'], 'debit_souhaite_m3h': 1,
                'kwc': devis['champ']['kwc']}

    def _stocke(self):
        self.calepinage.refresh_from_db()
        return (self.calepinage.resultat or {}).get('pompage_dernier')

    def test_acal831_post_complet_enregistre_le_dernier_rendu(self):
        donnees = self._calepinage(self._complet())
        self.assertTrue(donnees['enregistre'])
        self.assertIsNone(donnees['motif_non_enregistre'])
        stocke = self._stocke()
        self.assertEqual(set(stocke),
                         set(CONTRAT_CALEPINAGE['exemple_enregistre']))
        self.assertEqual(stocke['volumes'], donnees['volumes'])
        self.assertNotIn('calepinage', stocke)
        self.assertNotIn('erreurs', stocke)
        self.assertNotIn('"prix', json.dumps(stocke))  # aucune clé « prix »
        # un nouveau POST remplace le précédent
        second = self._calepinage(dict(self._complet(), heures_pompage=5))
        self.assertTrue(second['enregistre'])
        self.assertEqual(self._stocke()['entrees']['heures_pompage'], 5.0)

    def test_acal831_post_incomplet_n_ecrit_rien(self):
        donnees = self._calepinage({'hmt_saisie': None})
        self.assertFalse(donnees['enregistre'])
        self.assertIn('debit_souhaite_m3h', donnees['motif_non_enregistre'])
        self.assertIsNone(self._stocke())

    def test_acal831_verrou_refuse_rien_ecrit_motif_mot_pour_mot(self):
        from unittest import mock

        from apps.calepinage.services.verrou import VerrouilleRefuse

        motif = 'Devis accepté : révisez-le (nouvelle version).'
        with mock.patch('apps.calepinage.services.verrou.verifier_ecriture_autorisee',
                        side_effect=VerrouilleRefuse(motif, champ='pompage')):
            donnees = self._calepinage(self._complet())
        self.assertFalse(donnees['enregistre'])
        self.assertEqual(donnees['motif_non_enregistre'], motif)
        self.assertIsNotNone(donnees['volumes'])  # le calcul reste servi
        self.assertIsNone(self._stocke())

    def test_acal831_lecteur_seul_calcule_sans_enregistrer(self):
        role = Role.objects.create(company=self.co, nom='Lecteur calepinage',
                                   permissions=['calepinage_voir'])
        lecteur = User.objects.create_user(
            username='agr125_lecteur', password='x', company=self.co, role=role)
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(lecteur)}')
        donnees = self._calepinage(self._complet())
        self.assertFalse(donnees['enregistre'])
        self.assertEqual(donnees['motif_non_enregistre'],
                         'droit calepinage_gerer manquant')
        self.assertIsNone(self._stocke())

    def test_corps_json_seul_multipart_415(self):
        """api-fuzz #997 : le schéma ne propose que JSON (un multipart ne sait
        pas porter ``null`` : « None » était lu comme texte → faux 400)."""
        url = f'/api/django/calepinage/calepinages/{self.calepinage.pk}/pompage/'
        rep = self.api.post(url, {'kwc': '1'}, format='multipart')
        self.assertEqual(rep.status_code, 415, rep.content[:300])

    def test_acal1113_alertes_de_pose_du_devis_sur_la_pompe_retenue(self):
        """ACAL1113 — calage sous l'immersion ⇒ alerte sous
        ``profondeur_calage_m`` ; pompe plus large que le tubage ⇒ alerte sous
        ``diametre_tubage_mm`` ; mêmes messages que ``choisir_pompe`` (règle
        UNIQUE ``alertes_pose_pompe``) ; sans saisie ⇒ [] ; pompe servie
        inchangée. Mutant : préfixe ``source.`` dans la vue ⇒ rouge."""
        from core.pompage.selection import alertes_pose_pompe
        avant = self._calepinage(self._complet())
        self.assertEqual(avant['alertes'], [])
        FicheTechnique.objects.create(
            company=self.co, produit=self.pompe, type_fiche='pompe',
            pompe_immersion_min_m=Decimal('5'), pompe_diametre_ext_mm=Decimal('150'))
        saisie = {'profondeur_calage_m': 42, 'niveau_dynamique_m': 40, 'diametre_tubage_mm': 150}
        donnees = self._calepinage(dict(self._complet(), **saisie))
        self.assertEqual(donnees['pompe'], avant['pompe'])
        self.assertEqual([(a['code'], a['champ']) for a in donnees['alertes']],
                         [('diametre_tubage', 'diametre_tubage_mm'),
                          ('immersion_minimale', 'profondeur_calage_m')])
        attendues = alertes_pose_pompe({'pompe_immersion_min_m': 5, 'pompe_diametre_ext_mm': 150}, **saisie)
        self.assertEqual(donnees['alertes'], attendues)
        self.assertEqual(donnees['entrees']['profondeur_calage_m'], 42.0)
        self.assertEqual(self._calepinage(self._complet())['alertes'], [])

    def test_acal1114_plafond_du_forage_et_bilan_du_reservoir(self):
        """ACAL1114 — débit d'exploitation trop bas ⇒ ``plafond_atteint`` et
        alerte sous ``debit_exploitation_m3h`` ; sans réservoir ⇒ bilan
        ``calcule: false`` + motif ; réservoir et besoin ⇒ bilan calculé ;
        sans débit d'exploitation ⇒ aucun plafond. Mutant : ne pas transmettre
        ``plafond_m3h`` ⇒ rouge."""
        sans = self._calepinage(dict(self._complet(), besoin_m3_jour=40))
        self.assertIsNone(sans['volumes']['plafond_forage_m3h'])
        self.assertFalse(sans['volumes']['plafond_atteint'])
        self.assertEqual(sans['bilan_reservoir']['calcule'], False)
        self.assertEqual(sans['bilan_reservoir']['motif'], 'aucun réservoir déclaré')
        bas = self._calepinage(dict(self._complet(), debit_exploitation_m3h=2,
                                    volume_reservoir_m3=30, besoin_m3_jour=40))
        self.assertEqual(bas['volumes']['plafond_forage_m3h'], 2.0)
        self.assertTrue(bas['volumes']['plafond_atteint'])
        self.assertIn(('plafond_forage', 'debit_exploitation_m3h'),
                      [(a['code'], a['champ']) for a in bas['alertes']])
        self.assertTrue(bas['bilan_reservoir']['calcule'])
        self.assertEqual(len(bas['bilan_reservoir']['jours_manque_mois']), 12)
        self.assertEqual(bas['entrees']['debit_exploitation_m3h'], 2.0)
        self.assertEqual(set(bas['bilan_reservoir']),
                         set(CONTRAT_CALEPINAGE['exemple']['bilan_reservoir']))
        # part du forage réglée par la société : 50 % de 4 m³/h = 2 m³/h
        CompanyProfile.objects.filter(company=self.co).update(agricole_part_debit_forage_pct=Decimal('50'))
        regle = self._calepinage(dict(self._complet(), debit_exploitation_m3h=4))
        self.assertEqual(regle['volumes']['plafond_forage_m3h'], 2.0)

    def test_acal815_comparaison_pompage_direct_contre_reservoir(self):
        """ACAL815 — 12 mois de besoin, 2 h de demande, réservoir déclaré ⇒
        débit direct > débit avec réservoir (heures-pic PVGIS) ; sans heures ⇒
        ``direct: null`` + motif nommé. Mutant : intervertir les options ⇒ rouge."""
        corps = dict(self._complet(), besoin_m3_mois=[300.0] * 12, volume_reservoir_m3=30)
        deux = self._calepinage(dict(corps, heures_demande_h=2))['comparaison_reservoir']
        self.assertEqual(set(deux), set(CONTRAT_CALEPINAGE['exemple']['comparaison_reservoir']))
        direct, avec = deux['direct'], deux['avec_reservoir']
        self.assertIsNotNone(direct)
        self.assertIsNotNone(avec)
        self.assertGreater(direct['debit_conception_m3h'], avec['debit_conception_m3h'])
        self.assertEqual(set(direct), set(CONTRAT_CALEPINAGE['exemple']['comparaison_reservoir']['direct']))
        sans = self._calepinage(corps)['comparaison_reservoir']
        self.assertIsNone(sans['direct'])
        self.assertIsNotNone(sans['avec_reservoir'])
        self.assertEqual(sans['motif'], 'fenêtre de demande non saisie')

    def test_acal821_plusieurs_pompes_sur_le_variateur_retenu(self):
        """ACAL821 — plaque du variateur SERVI (7,5 kW dans ce catalogue) : 4 ×
        1,1 kW conformes dans les deux modes ; 7 × 1,1 ensemble ⇒ ``depasse``,
        à tour de rôle ⇒ conforme ; sans mode ⇒ ``non_verifiable`` ; sans liste ⇒
        absent. Mutant : toujours sommer ⇒ rouge sur « à tour de rôle »."""
        def bloc(nb, mode=None):
            corps = dict(self._complet(), pompes_variateur=[{'nom': f'P{i}', 'kw': 1.1} for i in range(nb)])
            if mode:
                corps['mode_pompes'] = mode
            return self._calepinage(corps)
        quatre = bloc(4, 'ensemble')
        self.assertEqual(quatre['variateur']['produit'], self.variateur.pk)
        self.assertEqual(set(quatre['pompes_variateur']), set(CONTRAT_CALEPINAGE['exemple']['pompes_variateur']))
        self.assertEqual(quatre['pompes_variateur']['verdict'], 'conforme')
        self.assertEqual(quatre['pompes_variateur']['kw_demande'], 4.4)
        self.assertEqual(quatre['pompes_variateur']['kw_variateur'], 7.5)
        self.assertEqual(bloc(4, 'a_tour_de_role')['pompes_variateur']['verdict'], 'conforme')
        self.assertEqual(bloc(7, 'ensemble')['pompes_variateur']['verdict'], 'depasse')
        tour = bloc(7, 'a_tour_de_role')['pompes_variateur']
        self.assertEqual((tour['verdict'], tour['kw_demande']), ('conforme', 1.1))
        self.assertEqual(bloc(4)['pompes_variateur']['verdict'], 'non_verifiable')
        self.assertIsNone(self._calepinage(self._complet())['pompes_variateur'])
        url = f'/api/django/calepinage/calepinages/{self.calepinage.pk}/pompage/'
        rep = self.api.post(url, {'mode_pompes': 0}, format='json')
        self.assertEqual(rep.status_code, 400, rep.content[:300])

    def test_acal820_appoint_sur_le_bus_dc_du_variateur_retenu(self):
        """ACAL820 — fiche à bus 400 V d'essai, 11 modules (Vmp à chaud ≈ 370 V)
        ⇒ ``vmp_sous_bus`` ; sans bus publié ⇒ ``non_verifiable`` nommant
        ``var_bus_dc_redresse_v`` ; sans appoint ⇒ absent. Mutant : verdict
        ``conforme`` par défaut ⇒ rouge."""
        Calepinage.objects.filter(pk=self.calepinage.pk).update(
            resultat={'entree_electrique': {'module_produit': self.panneau.pk}})
        corps = dict(self._complet(), modules_en_serie=11, appoint='reseau')
        sans_bus = self._calepinage(corps)['appoint_variateur']
        self.assertEqual(set(sans_bus), set(CONTRAT_CALEPINAGE['exemple']['appoint_variateur']))
        self.assertEqual(sans_bus['verdict'], 'non_verifiable')
        self.assertIn('var_bus_dc_redresse_v', sans_bus['motif'])
        FicheTechnique.objects.filter(produit=self.variateur).update(
            var_bus_dc_redresse_v=Decimal('400'))
        bloc = self._calepinage(corps)['appoint_variateur']
        self.assertEqual((bloc['verdict'], bloc['appoint']), ('vmp_sous_bus', 'reseau'))
        self.assertLess(bloc['vmp_chaud_v'], 400)
        self.assertEqual(bloc['bus_redresse_v'], 400.0)
        self.assertIsNone(self._calepinage(dict(corps, appoint=''))['appoint_variateur'])
        self.assertIsNone(self._calepinage(self._complet())['appoint_variateur'])


class PariteHmtTest(TestCase):
    """La HMT du calepinage est celle de ``hmt_composantes`` (AGR111)."""

    def test_meme_hmt_que_le_noyau(self):
        entrees = dict(niveau_statique_m=32, rabattement_specifique_m_par_m3h=0.25,
                       denivele_m=4, longueur_conduite_m=350,
                       diametre_interieur_mm=100, materiau_conduite='pehd',
                       pertes_singulieres_m=0.8, pression_service_bar=1.0,
                       debit_m3h=30)
        noyau = hmt_composantes(**entrees)
        ecran = hmt_du_puits(
            niveau_statique_m=32, coefficient_rabattement_m_par_m3h=0.25,
            hauteur_refoulement_m=4, longueur_tuyauterie_m=350,
            diametre_interieur_mm=100, materiau_conduite='pehd',
            pertes_singulieres_m=0.8, pression_service_bar=1.0, debit_m3h=30)
        self.assertEqual(ecran['source'], 'calculee')
        self.assertEqual(ecran['hmt_m'], noyau['valeur_m'])
        self.assertEqual(ecran['composantes'], noyau['composantes'])

    def test_composante_manquante_saisie_et_nommee(self):
        ecran = hmt_du_puits(hmt_saisie=55, niveau_statique_m=32,
                             coefficient_rabattement_m_par_m3h=0.25,
                             hauteur_refoulement_m=4, longueur_tuyauterie_m=350,
                             coefficient_frottement=0.0001, debit_m3h=30)
        self.assertEqual(ecran['source'], 'saisie')
        self.assertEqual(ecran['hmt_m'], 55)
        self.assertIn('pertes_singulieres_m', ecran['manquantes'])
        self.assertIn('pression_service_m', ecran['manquantes'])
