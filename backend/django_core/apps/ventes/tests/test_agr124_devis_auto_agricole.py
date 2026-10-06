# -*- coding: utf-8 -*-
"""AGR124 — devis automatique AGRICOLE par le serveur (bouton « Devis
automatique » de la fiche lead).

Chemin RÉEL ``POST /api/django/ventes/devis/auto/`` → ``build_devis_auto`` →
``pompage.etudier_pompage`` → kit minimum → devis brouillon → étude v2 écrite
une fois (AGR123). Seul le RÉSEAU est simulé (PVGIS / TMY, patron AGR121).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_agr124_devis_auto_agricole"
"""
from datetime import date
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Lead
from apps.parametres.models import CompanyProfile
from apps.stock.models import FicheTechnique, Produit
from apps.ventes.domain import pompage
from apps.ventes.models import Devis
from authentication.models import Company

User = get_user_model()

AUTO_URL = '/api/django/ventes/devis/auto/'
_JOUR = ([0] * 6 + [100, 300, 500, 700, 850, 950, 1000, 950, 850, 700, 500,
                    300, 100] + [0] * 5)
PROFILS = [[g * (0.7 + 0.05 * i) for g in _JOUR] for i in range(12)]
COURBE = {'debits_m3h': [0, 12, 24, 30, 36, 39],
          'hmt_m': [91, 85, 70, 60, 43, 34]}


class DevisAutoAgricoleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.co = Company.objects.get_or_create(
            slug='agr124-co', defaults={'nom': 'AGR124 Co'})[0]
        profil, _ = CompanyProfile.objects.get_or_create(company=cls.co)
        CompanyProfile.objects.filter(pk=profil.pk).update(
            agricole_pump_hours=Decimal('7'))
        cls.variateur = cls._produit(
            'VARIATEUR VEICHI SI23 5.5KW 380V', '6000',
            role_pompage='variateur_pompage', alimentation='tri',
            pompe_kw=Decimal('5.5'), tension_v=380)
        FicheTechnique.objects.create(
            company=cls.co, produit=cls.variateur,
            type_fiche='variateur_pompage', ond_mppt_v_min=Decimal('250'),
            ond_mppt_v_max=Decimal('750'), ond_v_max_abs=Decimal('800'),
            ond_i_max_mppt_a=Decimal('20'), ond_phases=3,
            var_v_sortie_v=Decimal('380'))
        cls.panneau = cls._produit('Panneau 710W', '1100')
        FicheTechnique.objects.create(
            company=cls.co, produit=cls.panneau, type_fiche='module',
            pmax_wc=Decimal('710'), vmp_v=Decimal('40'), voc_v=Decimal('48'),
            isc_a=Decimal('18'), imp_a=Decimal('17'))

    @classmethod
    def _produit(cls, nom, prix, **kw):
        return Produit.objects.create(
            company=cls.co, nom=nom, prix_vente=Decimal(prix),
            prix_achat=Decimal('1'), **kw)

    def _pompe(self, prix):
        return self._produit(
            'Pompe immergée OSP 30/8 7,5 CV 380V', prix,
            role_pompage='pompe', type_pompe='immergee', alimentation='tri',
            pompe_kw=Decimal('5.5'), pompe_cv=Decimal('7.5'), tension_v=380,
            courbe_pompe=COURBE)

    def setUp(self):
        self.user = User.objects.create_user(
            username='agr124_user', password='x', role_legacy='responsable',
            company=self.co)
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)
        for cible, valeur in (('profils_horaires_site', PROFILS),
                              ('temperatures_du_site', None)):
            patcher = mock.patch.object(pompage, cible, return_value=valeur)
            patcher.start()
            self.addCleanup(patcher.stop)

    def _lead(self, **extra):
        champs = dict(
            company=self.co, nom='Ferme', prenom='AGR124',
            email='agr124@example.com', type_installation='agricole',
            raccordement='triphase', ville='Taroudant',
            gps_lat=Decimal('30.47'), gps_lng=Decimal('-8.88'),
            pompe_hmt_m=Decimal('60'), besoin_eau_m3j=Decimal('135'),
            niveau_statique_m=Decimal('35'), debit_forage_m3h=Decimal('50'))
        champs.update(extra)
        return Lead.objects.create(**champs)

    def _post(self, lead):
        return self.api.post(AUTO_URL, {'lead': lead.id}, format='json')

    def test_sans_niveau_ni_debit_forage_422_d_agr_4(self):
        self._pompe('15000')
        lead = self._lead(niveau_statique_m=None, debit_forage_m3h=None)
        rep = self._post(lead)
        self.assertEqual(rep.status_code, 422, rep.data)
        self.assertIn('D-AGR-4', rep.data['detail'])
        self.assertIn("relevé du point d'eau", rep.data['detail'].lower())
        self.assertFalse(Devis.objects.filter(lead=lead).exists())

    def test_donnee_hydraulique_manquante_422_nommant_le_champ(self):
        self._pompe('15000')
        lead = self._lead(pompe_hmt_m=None, niveau_statique_m=None)
        rep = self._post(lead)
        self.assertEqual(rep.status_code, 422, rep.data)
        self.assertEqual(rep.data['field'], 'pompe_hmt_m')
        self.assertFalse(Devis.objects.filter(lead=lead).exists())

    def test_lead_complet_devis_brouillon_ligne_pompe_et_etude_v2(self):
        pompe = self._pompe('15000')
        lead = self._lead()
        rep = self._post(lead)
        self.assertEqual(rep.status_code, 201, rep.data)
        self.assertIsInstance(rep.data['alertes'], list)
        devis = Devis.objects.get(pk=rep.data['id'])
        self.assertEqual(devis.statut, 'brouillon')
        self.assertEqual(devis.mode_installation, 'agricole')
        self.assertTrue(devis.lignes.filter(produit=pompe).exists())
        self.assertTrue(devis.lignes.filter(produit=self.variateur).exists())
        # Aucune distance saisie ⇒ aucune ligne câble DC.
        self.assertFalse(devis.lignes.filter(
            designation__icontains='câble dc').exists())
        etude = devis.etude_params
        self.assertEqual(etude['taille'], 'recommandee')
        self.assertEqual(etude['alim'], 'tri')
        self.assertEqual(etude['pompe_kw'], 5.5)
        self.assertIsNotNone(etude.get('champ_kwc'))
        self.assertIn('_empreinte', etude['provenance_pompage'])
        lead.refresh_from_db()
        self.assertEqual(lead.type_installation, 'agricole')

    def test_lead_butane_saisies_economie_provenance_lead(self):
        self._pompe('15000')
        lead = self._lead(
            pompe_alim_actuelle='butane',
            butane_bouteilles_jour=Decimal('4'),
            carburant_prix_unitaire_mad=Decimal('50'),
            carburant_prix_declare_le=date(2026, 9, 12),
            mois_irrigation=[4, 5, 6, 7, 8, 9])
        rep = self._post(lead)
        self.assertEqual(rep.status_code, 201, rep.data)
        saisies = Devis.objects.get(
            pk=rep.data['id']).etude_params['saisies_economie_pompage']
        self.assertEqual(saisies['energie_actuelle']['valeur'], 'butane')
        self.assertEqual(saisies['energie_actuelle']['provenance']['origine'],
                         'lead')
        self.assertEqual(saisies['consommation']['quantite'], 4)
        self.assertEqual(saisies['consommation']['unite'], 'bouteille_12kg')
        self.assertEqual(saisies['depense_unitaire_payee'],
                         {'valeur': 50, 'saisi_le': '2026-09-12'})
        self.assertEqual(saisies['mois_irrigation']['mois'],
                         [4, 5, 6, 7, 8, 9])
        self.assertEqual(saisies['mois_irrigation']['provenance']['origine'],
                         'lead')

    def test_seules_des_osp_a_prix_zero_422_nommant_la_cause(self):
        self._pompe('0')
        lead = self._lead()
        rep = self._post(lead)
        self.assertEqual(rep.status_code, 422, rep.data)
        self.assertIn('Aucune pompe chiffrable', rep.data['detail'])
        self.assertIn('OSP 30/8', rep.data['detail'])
        self.assertEqual(rep.data['field'], 'pompe')
        self.assertFalse(Devis.objects.filter(lead=lead).exists())

    def test_tunnel_agricole_toujours_refuse(self):
        from apps.ventes.services import AutoDevisError, build_devis_auto
        self._pompe('15000')
        lead = self._lead()
        with self.assertRaises(AutoDevisError) as ctx:
            build_devis_auto(lead=lead, user=self.user, company=self.co,
                             origine='tunnel')
        self.assertEqual(ctx.exception.field, 'type_installation')
        self.assertFalse(Devis.objects.filter(lead=lead).exists())
