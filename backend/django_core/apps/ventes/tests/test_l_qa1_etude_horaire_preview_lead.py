# -*- coding: utf-8 -*-
"""L-QA1 (24/08/2026) FIX1 — POST /ventes/etude-horaire/preview/ avec un
``lead`` (aucun devis persisté, écran GÉNÉRATEUR).

Preuve de bug live (audit navigateur 24/08/2026) : la même requête sans
``lead`` répondait ``profil.occupation: null`` et
``profil.equipements_actifs: []`` alors que le lead lié portait un script
d'appel complet (occupation_jour='present', VE/clim/piscine/chauffe-eau
renseignés) — le commercial ne voyait donc jamais l'effet réel de ces
réponses avant l'enregistrement du devis. Ce module épingle le correctif :
``lead`` résout le MÊME profil que le chemin ``devis`` (mêmes sélecteurs
CRM), scopé société, avec ``devis`` toujours prioritaire quand les deux sont
fournis.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_l_qa1_etude_horaire_preview_lead"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client, Lead
from apps.ventes.models import Devis

User = get_user_model()


class _LeadPreviewBase(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='lqa1-co', defaults={'nom': 'L-QA1 Co'})
        self.other_company, _ = Company.objects.get_or_create(
            slug='lqa1-other', defaults={'nom': 'L-QA1 Other'})
        self.user = User.objects.create_user(
            username='lqa1_user', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _lead_complet(self, *, company=None, ville='Casablanca'):
        return Lead.objects.create(
            company=company or self.company, nom='Lead', prenom='Complet',
            telephone='+212600000090', ville=ville,
            facture_hiver=Decimal('1800'), ete_differente=False,
            occupation_jour='present',
            equip_voiture_electrique=True, equip_ve_chargeur_kw=7.4,
            equip_ve_creneau='nuit', equip_ve_km_semaine=150,
            equip_clim=True, equip_clim_kw=5, equip_clim_pieces=3,
            equip_piscine=True, equip_piscine_pompe_kw=1.1,
            equip_piscine_heures_jour=6,
            equip_chauffe_eau_electrique=True, equip_chauffe_eau_kw=2.4,
            equip_chauffe_eau_creneau='soir')


class PreviewAvecLeadTests(_LeadPreviewBase):
    def test_lead_seul_pose_occupation_et_equipements_actifs(self):
        """LE BUG LIVE : sans ce correctif, occupation=None et
        equipements_actifs=[] même avec un script d'appel complet."""
        lead = self._lead_complet()
        resp = self.api.post('/api/django/ventes/etude-horaire/preview/', {
            'mode_installation': 'residentiel', 'lead': lead.id,
            'dimensionner': False,
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        profil = resp.data['profil']
        self.assertEqual(profil['occupation'], 'presence_jour')
        self.assertEqual(
            set(profil['equipements_actifs']),
            {'ve', 'clim', 'piscine', 'chauffe_eau'})

    def test_lead_seul_ancre_la_consommation_sans_facture_dans_le_corps(self):
        """Le lead porte sa PROPRE facture d'hiver : aucune facture à
        retaper dans le corps de la requête pour ancrer un calcul."""
        lead = self._lead_complet()
        resp = self.api.post('/api/django/ventes/etude-horaire/preview/', {
            'mode_installation': 'residentiel', 'lead': lead.id,
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['consommation']['source'], 'facture_hiver')
        self.assertTrue(any(v > 0 for v in resp.data['consommation']['kwh_mensuels']))

    def test_estimation_conso_presente_avec_equipements_actifs(self):
        """T4/L-QA1 — la décomposition mensuelle apparaît dès qu'au moins une
        couche équipement est active, absente du payload avant ce correctif."""
        lead = self._lead_complet()
        resp = self.api.post('/api/django/ventes/etude-horaire/preview/', {
            'mode_installation': 'residentiel', 'lead': lead.id,
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        estimation = resp.data.get('estimation_conso')
        self.assertIsNotNone(estimation)
        self.assertEqual(len(estimation['base_mensuelle']), 12)
        self.assertEqual(len(estimation['totale_mensuelle']), 12)
        self.assertTrue(estimation['ajouts'])

    def test_devis_prime_toujours_sur_un_lead_fourni_en_meme_temps(self):
        """Un devis existant reste la source de vérité — même chaîne que le
        serveur pour la résolution `devis` avant `lead`."""
        lead_devis = self._lead_complet(ville='Rabat')
        lead_devis.occupation_jour = 'absent'
        lead_devis.equip_clim = False
        lead_devis.save()
        client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Devis')
        devis = Devis.objects.create(
            company=self.company, reference='DEV-LQA1-01',
            client=client_obj, lead=lead_devis, statut='brouillon',
            taux_tva=Decimal('20'), mode_installation='residentiel')
        lead_autre = self._lead_complet(ville='Casablanca')

        resp = self.api.post('/api/django/ventes/etude-horaire/preview/', {
            'mode_installation': 'residentiel',
            'devis': devis.id, 'lead': lead_autre.id,
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        # Le profil lu est celui du devis (absent, aucun équipement actif),
        # jamais celui du lead fourni en plus.
        self.assertEqual(resp.data['profil']['occupation'], 'absence_jour')

    def test_lead_dune_autre_societe_est_ignore_et_averti(self):
        """IDOR : un id de lead d'une autre société ne doit jamais faire
        fuiter son profil — repli sur le corps brut, avec avertissement."""
        lead_etranger = self._lead_complet(company=self.other_company)
        resp = self.api.post('/api/django/ventes/etude-horaire/preview/', {
            'mode_installation': 'residentiel', 'lead': lead_etranger.id,
            'facture_hiver': 1000,
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertIsNone(resp.data['profil']['occupation'])
        self.assertTrue(any(
            'introuvable' in a.lower() for a in resp.data['avertissements']))

    def test_sans_lead_ni_devis_comportement_byte_identique_au_corps_brut(self):
        """Non-régression : le chemin historique (corps brut) est inchangé."""
        resp = self.api.post('/api/django/ventes/etude-horaire/preview/', {
            'mode_installation': 'residentiel', 'facture_hiver': 1200,
            'occupation': 'presence_jour',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['profil']['occupation'], 'presence_jour')
        self.assertEqual(resp.data['profil']['equipements_actifs'], [])
        self.assertIsNone(resp.data['estimation_conso'])
