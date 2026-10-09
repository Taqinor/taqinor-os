"""ACHT37 (C-ACHT-033/034) — la poussée des n° de série vers le parc SAV est
un geste explicite (clôture de l'intervention), un GET n'écrit rien ; un n°
en double est refusé à la saisie ; un relevé déjà poussé ne se corrige plus
(409).

Rejoue CINT-10 / CINT-11 (GET du Viewer crée l'équipement ; doublon → 500).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht_series_parc"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.installations.models import (
    ComponentSerial, Installation, Intervention,
)
from apps.sav.models import Equipement
from apps.stock.models import Produit

User = get_user_model()
BASE = '/api/django/installations/interventions'


class SeriesParcTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-acht37', defaults={'nom': 'Co ACHT37'})
        self.user = User.objects.create_user(
            username='resp-acht37', password='x', company=self.company,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur ACHT37', sku='OND-ACHT37',
            prix_vente=Decimal('1000'), quantite_stock=5)
        self.inst = Installation.objects.create(
            company=self.company, reference='CH-ACHT37')
        self.iv = Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='pose', created_by=self.user,
            technicien=self.user, statut=Intervention.Statut.SUR_SITE)
        self.serial = ComponentSerial.objects.create(
            company=self.company, intervention=self.iv, produit=self.produit,
            numero_serie='SN-1', created_by=self.user)

    def _equipements(self):
        return Equipement.objects.filter(
            company=self.company, numero_serie='SN-1').count()

    def test_get_compte_rendu_sans_ecriture(self):
        r = self.api.get(f'{BASE}/{self.iv.id}/compte-rendu/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self._equipements(), 0)
        self.serial.refresh_from_db()
        self.assertFalse(self.serial.pousse_parc)

    def test_doublon_refuse_400(self):
        r = self.api.post(f'{BASE}/{self.iv.id}/ajouter-serial/', {
            'produit': self.produit.id, 'numero_serie': 'SN-1'},
            format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('numero_serie', r.data)
        self.assertEqual(ComponentSerial.objects.filter(
            numero_serie='SN-1').count(), 1)

    def test_poussee_a_la_cloture(self):
        r = self.api.patch(f'{BASE}/{self.iv.id}/', {'statut': 'terminee'},
                           format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(self._equipements(), 1)
        self.serial.refresh_from_db()
        self.assertTrue(self.serial.pousse_parc)

    def test_correction_apres_poussee_refusee(self):
        self.api.patch(f'{BASE}/{self.iv.id}/', {'statut': 'terminee'},
                       format='json')
        r = self.api.post(f'{BASE}/{self.iv.id}/modifier-serial/', {
            'serial': self.serial.id, 'numero_serie': 'SN-CORRECT'},
            format='json')
        self.assertEqual(r.status_code, 409, r.data)
        self.assertIn('Série déjà au parc SAV', str(r.data))
        r = self.api.post(f'{BASE}/{self.iv.id}/supprimer-serial/',
                          {'serial': self.serial.id}, format='json')
        self.assertEqual(r.status_code, 409, r.data)
        self.serial.refresh_from_db()
        self.assertEqual(self.serial.numero_serie, 'SN-1')
        self.assertEqual(self._equipements(), 1)
