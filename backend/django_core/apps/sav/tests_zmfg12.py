"""ZMFG12 — Motif de mise au rebut d'un équipement + statut « au rebut ».

Couvre :
  * mise au rebut motivée (motif obligatoire) exclut l'équipement du parc
    actif par défaut ;
  * réactivation possible (retour au parc actif) ;
  * un équipement au rebut ne génère plus de ticket préventif par
    franchissement de seuil (XSAV17) ;
  * permission (responsable/admin) testée.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_zmfg12 -v 2
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.stock.models import Produit
from apps.sav.models import Equipement, Ticket
from apps.sav.services import enregistrer_releve_compteur

User = get_user_model()


def make_company(slug='sav-zmfg12', nom='Sav Co ZMFG12'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ZMFG12MiseAuRebutTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='zmfg12_admin', password='x', role_legacy='admin',
            company=self.company)
        self.viewer = User.objects.create_user(
            username='zmfg12_viewer', password='x', role_legacy='normal',
            company=self.company)
        self.api = auth(self.admin)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ZMFG12',
            email='zmfg12-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-ZMFG12', client=self.client_obj)
        self.produit = Produit.objects.create(
            company=self.company, nom='Pompe Z', sku='POMPE-Z-ZMFG12',
            prix_achat=300, prix_vente=600)

    def _equip(self, **kwargs):
        defaults = dict(
            company=self.company, produit=self.produit, installation=self.inst,
            created_by=self.admin)
        defaults.update(kwargs)
        return Equipement.objects.create(**defaults)

    def test_motif_obligatoire(self):
        eq = self._equip()
        r = self.api.post(
            f'/api/django/sav/equipements/{eq.id}/mettre-au-rebut/',
            {}, format='json')
        self.assertEqual(r.status_code, 400, r.data)

    def test_mise_au_rebut_exclut_du_parc_actif(self):
        eq = self._equip()
        r = self.api.post(
            f'/api/django/sav/equipements/{eq.id}/mettre-au-rebut/',
            {'motif': 'Fin de vie — casse irréparable'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        eq.refresh_from_db()
        self.assertTrue(eq.mis_au_rebut)
        self.assertIsNotNone(eq.date_rebut)
        self.assertEqual(eq.motif_rebut, 'Fin de vie — casse irréparable')

        r_list = self.api.get('/api/django/sav/equipements/')
        rows = r_list.data['results'] if isinstance(
            r_list.data, dict) else r_list.data
        ids = [row['id'] for row in rows]
        self.assertNotIn(eq.id, ids)

        r_only = self.api.get(
            '/api/django/sav/equipements/', {'rebut': 'only'})
        rows_only = r_only.data['results'] if isinstance(
            r_only.data, dict) else r_only.data
        ids_only = [row['id'] for row in rows_only]
        self.assertIn(eq.id, ids_only)

        r_tous = self.api.get(
            '/api/django/sav/equipements/', {'rebut': 'tous'})
        rows_tous = r_tous.data['results'] if isinstance(
            r_tous.data, dict) else r_tous.data
        ids_tous = [row['id'] for row in rows_tous]
        self.assertIn(eq.id, ids_tous)

    def test_reactivation_possible(self):
        eq = self._equip(
            mis_au_rebut=True, date_rebut=date(2026, 1, 1), motif_rebut='x')
        r = self.api.post(
            f'/api/django/sav/equipements/{eq.id}/reactiver-rebut/',
            {}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        eq.refresh_from_db()
        self.assertFalse(eq.mis_au_rebut)
        self.assertIsNone(eq.date_rebut)

    def test_permission_reservee_responsable_admin(self):
        eq = self._equip()
        r = auth(self.viewer).post(
            f'/api/django/sav/equipements/{eq.id}/mettre-au-rebut/',
            {'motif': 'x'}, format='json')
        self.assertEqual(r.status_code, 403, r.data)

    def test_equipement_au_rebut_ne_genere_plus_de_preventif(self):
        equip = self._equip(entretien_toutes_les_heures=Decimal('500'))
        self.api.post(
            f'/api/django/sav/equipements/{equip.id}/mettre-au-rebut/',
            {'motif': 'Fin de vie'}, format='json')
        equip.refresh_from_db()

        _, ticket = enregistrer_releve_compteur(
            company=self.company, equipement=equip, type_releve='heures',
            valeur=Decimal('600'), date_releve=date(2026, 1, 1),
            created_by=self.admin)
        self.assertIsNone(ticket)
        self.assertEqual(Ticket.objects.filter(equipement=equip).count(), 0)
