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
