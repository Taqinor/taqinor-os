"""ACHT52 (C-ACHT-052) — FK inscriptibles bornées à la société :
`GpsConsentRecordSerializer.technicien`, `LotPrelevementSerializer.operateur`,
`PickListLigneSerializer.bin`, `OrdreAssemblageSerializer.chantier` /
`.ordre_sous_traitance`, `ProjetSerializer.responsable` — un id d'une autre
société donne 400 sans écriture ni nom renvoyé.

Rejoue CTEN-4 : GPS technicien=B 201, LOT operateur=B 200, PICKLIGNE bin=B
200, ORDRE chantier=B 201, PROGRAMME responsable=B 201.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht52_fk_corps_tenant"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.installations.models import (
    BinLocation, Installation, Kit, LotPrelevement, OrdreSousTraitance,
    PickList, PickListLigne,
)
from apps.stock.models import EmplacementStock, Fournisseur

User = get_user_model()
BASE = '/api/django/installations'


class FkCorpsTenantTests(TestCase):
    def setUp(self):
        self.co_a = Company.objects.create(nom='ACHT52 A', slug='acht52-a')
        self.co_b = Company.objects.create(nom='ACHT52 B', slug='acht52-b')
        self.admin = User.objects.create_user(
            username='admin-a-acht52', password='x', company=self.co_a,
            role_legacy='admin')
        self.user_a = User.objects.create_user(
            username='user-a-acht52', password='x', company=self.co_a,
            role_legacy='technicien')
        self.user_b = User.objects.create_user(
            username='user-b-SECRET', password='x', company=self.co_b,
            role_legacy='technicien')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        # Données de B.
        emp_b = EmplacementStock.objects.create(company=self.co_b, nom='Dépôt B')
        self.bin_b = BinLocation.objects.create(
            company=self.co_b, emplacement=emp_b, code='B-01')
        self.chantier_b = Installation.objects.create(
            company=self.co_b, reference='CH-B-ACHT52')
        four_b = Fournisseur.objects.create(company=self.co_b, nom='Four B')
        self.ordre_b = OrdreSousTraitance.objects.create(
            company=self.co_b, reference='OST-B', sous_traitant=four_b,
            prestation='x', montant=Decimal('1'))
        # Données de A.
        emp_a = EmplacementStock.objects.create(company=self.co_a, nom='Dépôt A')
        self.bin_a = BinLocation.objects.create(
            company=self.co_a, emplacement=emp_a, code='A-01')
        self.chantier_a = Installation.objects.create(
            company=self.co_a, reference='CH-A-ACHT52')
        self.lot_a = LotPrelevement.objects.create(
            company=self.co_a, reference='LOT-A')
        pick = PickList.objects.create(
            company=self.co_a, reference='PL-A', installation=self.chantier_a)
        self.ligne_a = PickListLigne.objects.create(
            pick_list=pick, designation='x', quantite_demandee=1)
        self.kit_a = Kit.objects.create(company=self.co_a, nom='Kit A')

    def _refus(self, r, champ):
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn(champ, r.data)
        self.assertNotIn('SECRET', str(r.data))

    def test_gps_technicien(self):
        r = self.api.post(f'{BASE}/gps-consentements/', {
            'technicien': self.user_b.id, 'consent_ref': 'CONS-1'},
            format='json')
        self._refus(r, 'technicien')
        r = self.api.post(f'{BASE}/gps-consentements/', {
            'technicien': self.user_a.id, 'consent_ref': 'CONS-2'},
            format='json')
        self.assertEqual(r.status_code, 201, r.data)

    def test_lot_operateur(self):
        r = self.api.patch(f'{BASE}/lots-prelevement/{self.lot_a.id}/',
                           {'operateur': self.user_b.id}, format='json')
        self._refus(r, 'operateur')
        self.lot_a.refresh_from_db()
        self.assertIsNone(self.lot_a.operateur_id)
        r = self.api.patch(f'{BASE}/lots-prelevement/{self.lot_a.id}/',
                           {'operateur': self.user_a.id}, format='json')
        self.assertEqual(r.status_code, 200, r.data)

    def test_pick_ligne_bin(self):
        r = self.api.patch(f'{BASE}/pick-list-lignes/{self.ligne_a.id}/',
                           {'bin': self.bin_b.id}, format='json')
        self._refus(r, 'bin')
        self.ligne_a.refresh_from_db()
        self.assertIsNone(self.ligne_a.bin_id)
        r = self.api.patch(f'{BASE}/pick-list-lignes/{self.ligne_a.id}/',
                           {'bin': self.bin_a.id}, format='json')
        self.assertEqual(r.status_code, 200, r.data)

    def test_ordre_assemblage_chantier_et_ordre_st(self):
        base = {'kit': self.kit_a.id, 'quantite': 1}
        r = self.api.post(f'{BASE}/ordres-assemblage/', {
            **base, 'chantier': self.chantier_b.id}, format='json')
        self._refus(r, 'chantier')
        r = self.api.post(f'{BASE}/ordres-assemblage/', {
            **base, 'ordre_sous_traitance': self.ordre_b.id}, format='json')
        self._refus(r, 'ordre_sous_traitance')
        r = self.api.post(f'{BASE}/ordres-assemblage/', {
            **base, 'chantier': self.chantier_a.id}, format='json')
        self.assertEqual(r.status_code, 201, r.data)

    def test_programme_responsable(self):
        r = self.api.post(f'{BASE}/programmes/', {
            'nom': 'Programme', 'responsable': self.user_b.id},
            format='json')
        self._refus(r, 'responsable')
        r = self.api.post(f'{BASE}/programmes/', {
            'nom': 'Programme', 'responsable': self.user_a.id},
            format='json')
        self.assertEqual(r.status_code, 201, r.data)
