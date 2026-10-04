"""AGR516 — GET /api/django/crm/leads/<id>/references-proches/.

Sélecteur ``parametres.selectors.realisations_proches`` (segment AGR513, tri
par distance haversine, distance inconnue en dernier) + action du lead,
bornée à la société, forme du contrat ``lead_references_proches.json``.
"""
import datetime
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Lead
from apps.parametres.models import CompanyProfile
from apps.parametres.models_realisations import Realisation

User = get_user_model()

CONTRAT = json.loads(
    (Path(__file__).resolve().parent / 'contract_samples'
     / 'lead_references_proches.json').read_text(encoding='utf-8'))


class ReferencesProchesTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AGR516', slug='agr516')
        CompanyProfile.objects.get_or_create(company=self.company)
        self.user = User.objects.create_user(
            username='agr516-resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.lead = Lead.objects.create(
            company=self.company, nom='Fellah', ville='Agadir',
            type_installation='agricole', telephone='+212600000516')

    def _real(self, ville, segment='agricole', **kw):
        return Realisation.objects.create(
            company=self.company, titre=f'Pompage {ville}', ville=ville,
            segment=segment, mise_en_service=datetime.date(2026, 6, 15),
            url_page=f'https://taqinor.ma/realisations/{ville.lower()}/',
            **kw)

    def _get(self, lead=None):
        lead = lead or self.lead
        return self.api.get(
            f'/api/django/crm/leads/{lead.pk}/references-proches/')

    def test_sans_realisation_agricole_liste_vide(self):
        self._real('Casablanca', segment='residentiel')  # jamais servie
        resp = self._get()
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data, CONTRAT['exemple_vide'])

    def test_triees_par_distance_inconnue_en_dernier(self):
        self._real('Marrakech')
        self._real('Zzzville')       # hors gazetier -> distance null
        self._real('Taroudant')
        resp = self._get()
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(set(resp.data), set(CONTRAT['exemple']))
        refs = resp.data['references']
        self.assertEqual([r['ville'] for r in refs],
                         ['Taroudant', 'Marrakech', 'Zzzville'])
        self.assertIsNone(refs[-1]['distance_km'])
        self.assertTrue(all(isinstance(r['distance_km'], int)
                            for r in refs[:2]))
        self.assertLess(refs[0]['distance_km'], refs[1]['distance_km'])
        for r in refs:
            self.assertEqual(set(r), set(CONTRAT['exemple']['references'][0]))
        self.assertEqual(refs[0]['mise_en_service'], '2026-06')
        self.assertEqual(resp.data['segment'], 'agricole')

    def test_limite_a_cinq(self):
        for _ in range(7):
            self._real('Taroudant')
        self.assertEqual(len(self._get().data['references']), 5)

    def test_une_realisation_inactive_n_est_pas_servie(self):
        self._real('Taroudant', actif=False)
        self.assertEqual(self._get().data['references'], [])

    def test_lead_d_une_autre_societe_404(self):
        autre = Company.objects.create(nom='Autre', slug='agr516-autre')
        lead = Lead.objects.create(
            company=autre, nom='Etranger', type_installation='agricole',
            telephone='+212600000517')
        self.assertEqual(self._get(lead).status_code, 404)
