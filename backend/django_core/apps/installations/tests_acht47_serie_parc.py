"""ACHT47 (C-ACHT-046/045) — le relevé de série passe par l'écrivain unique du
parc (`sav.services.assurer_equipement_chantier`) : date de pose = date de
réception, doublon refusé à la saisie (en ligne et en synchro) avec un message
lisible, un GET compte-rendu n'écrit rien, un conflit hérité n'est jamais un 500.

Rejoue CREC-4 / CREC-3.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht47_serie_parc"
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.installations import field_capture, field_sync
from apps.installations.models import (
    ComponentSerial, Installation, Intervention,
)
from apps.sav.models import Equipement
from apps.stock.models import Produit

User = get_user_model()
BASE = '/api/django/installations/interventions'
RECEPTION = date(2026, 9, 1)


class SerieParcTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-acht47', defaults={'nom': 'Co ACHT47'})
        self.user = User.objects.create_user(
            username='tech-acht47', password='x', company=self.company,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur ACHT47', sku='OND-ACHT47',
            prix_vente=Decimal('1000'), quantite_stock=5)
        self.inst = Installation.objects.create(
            company=self.company, reference='CH-ACHT47',
            date_reception=RECEPTION)
        self.iv = Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='pose', created_by=self.user,
            technicien=self.user, statut=Intervention.Statut.SUR_SITE)

    def _ajouter(self, serie):
        return self.api.post(f'{BASE}/{self.iv.id}/ajouter-serial/', {
            'produit': self.produit.id, 'numero_serie': serie},
            format='json')

    def test_doublon_saisie_400(self):
        Equipement.objects.create(
            company=self.company, produit=self.produit,
            installation=self.inst, numero_serie='SN-DUP',
            date_pose=RECEPTION)
        self.assertEqual(self._ajouter('SN-NEW').status_code, 201)
        r = self._ajouter('SN-NEW')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('déjà relevé', str(r.data['numero_serie']))
        r = self._ajouter('SN-DUP')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('déjà au parc', str(r.data['numero_serie']))
        self.assertEqual(ComponentSerial.objects.filter(
            numero_serie='SN-NEW').count(), 1)

    def test_doublon_sync_refuse(self):
        ComponentSerial.objects.create(
            company=self.company, intervention=self.iv, produit=self.produit,
            numero_serie='SN-NEW', created_by=self.user)
        with self.assertRaises(field_sync.FieldOpError) as ctx:
            field_sync._h_serial(self.company, self.user, {
                'intervention': self.iv.id, 'produit': self.produit.id,
                'numero_serie': 'SN-NEW'})
        self.assertIn('déjà relevé', str(ctx.exception))

    def test_get_compte_rendu_sans_ecriture(self):
        ComponentSerial.objects.create(
            company=self.company, intervention=self.iv, produit=self.produit,
            numero_serie='SN-GET', created_by=self.user)
        for _ in range(2):
            r = self.api.get(f'{BASE}/{self.iv.id}/compte-rendu/')
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r['Content-Type'], 'application/pdf')
        self.assertFalse(Equipement.objects.filter(
            company=self.company, numero_serie='SN-GET').exists())

    def test_conflit_herite_pas_500(self):
        # Deux relevés hérités 'SN-X' non poussés (contournent la garde).
        for _ in range(2):
            ComponentSerial.objects.create(
                company=self.company, intervention=self.iv,
                produit=self.produit, numero_serie='SN-X',
                created_by=self.user)
        resultat = field_capture.push_serials_to_parc(self.iv, self.user)
        self.assertEqual(int(resultat), 1)
        self.assertEqual(len(resultat.conflits), 1)
        self.assertEqual(Equipement.objects.filter(
            company=self.company, numero_serie='SN-X').count(), 1)
        self.assertEqual(self.iv.serials.filter(pousse_parc=False).count(), 1)

    def test_date_pose_reception(self):
        ComponentSerial.objects.create(
            company=self.company, intervention=self.iv, produit=self.produit,
            numero_serie='SN-NEW', created_by=self.user)
        r = self.api.patch(f'{BASE}/{self.iv.id}/', {'statut': 'terminee'},
                           format='json')
        self.assertEqual(r.status_code, 200, r.data)
        eq = Equipement.objects.get(
            company=self.company, numero_serie='SN-NEW')
        self.assertEqual(eq.date_pose, RECEPTION)
