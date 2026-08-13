"""NTCRM17 — Salle de vente digitale (Digital Sales Room) : modèle + CRUD +
endpoint public tokenisé."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Client, SalleVente, SalleVenteItem
from apps.roles.models import Role
from apps.ventes.models import Devis

User = get_user_model()


class SalleVenteModelTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor NTCRM17', slug='taqinor-ntcrm17')

    def test_clean_refuse_ni_lead_ni_client(self):
        salle = SalleVente(company=self.company, titre='Sans cible')
        with self.assertRaises(Exception):
            salle.full_clean()

    def test_clean_refuse_lead_et_client_simultanes(self):
        client = Client.objects.create(company=self.company, nom='C')
        from apps.crm.models import Lead
        lead = Lead.objects.create(company=self.company, nom='L')
        salle = SalleVente(company=self.company, titre='Double', lead=lead, client=client)
        with self.assertRaises(Exception):
            salle.full_clean()

    def test_mot_de_passe_jamais_stocke_en_clair(self):
        client = Client.objects.create(company=self.company, nom='C2')
        salle = SalleVente.objects.create(
            company=self.company, titre='Protégée', client=client)
        salle.set_password('secret123')
        salle.save()
        self.assertNotIn('secret123', salle.password_hash)
        self.assertTrue(salle.check_password('secret123'))
        self.assertFalse(salle.check_password('mauvais'))


class SalleVenteApiTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor NTCRM17b', slug='taqinor-ntcrm17b')
        self.role = Role.objects.create(
            company=self.company, nom='Responsable',
            permissions=['crm_creer', 'crm_modifier'])
        self.user = User.objects.create_user(
            username='resp_ntcrm17', password='x',
            company=self.company, role=self.role)
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.client_obj = Client.objects.create(company=self.company, nom='Client SV')

    def _create_salle(self, **extra):
        resp = self.api.post('/api/django/crm/salles-vente/', {
            'client': self.client_obj.pk, 'titre': 'Salle test', **extra,
        })
        self.assertEqual(resp.status_code, 201, resp.data)
        return resp.data

    def test_creer_et_ajouter_items(self):
        data = self._create_salle()
        salle_id = data['id']
        devis = Devis.objects.create(
            company=self.company, client=self.client_obj, reference='DVSV1',
            statut=Devis.Statut.ENVOYE)
        resp = self.api.post(
            f'/api/django/crm/salles-vente/{salle_id}/items/',
            {'type': 'devis', 'reference': str(devis.pk)})
        self.assertEqual(resp.status_code, 201, resp.data)
        resp2 = self.api.get(f'/api/django/crm/salles-vente/{salle_id}/')
        self.assertEqual(len(resp2.data['items']), 1)

    def test_public_endpoint_expose_2_devis_1_document_sans_prix_achat(self):
        data = self._create_salle()
        token = data['token']
        devis1 = Devis.objects.create(
            company=self.company, client=self.client_obj, reference='DVSV2',
            statut=Devis.Statut.ENVOYE)
        devis2 = Devis.objects.create(
            company=self.company, client=self.client_obj, reference='DVSV3',
            statut=Devis.Statut.ACCEPTE)
        salle = SalleVente.objects.get(token=token)
        SalleVenteItem.objects.create(salle=salle, type='devis', reference=str(devis1.pk))
        SalleVenteItem.objects.create(salle=salle, type='devis', reference=str(devis2.pk))
        SalleVenteItem.objects.create(salle=salle, type='document', reference='42')

        public_api = APIClient()
        resp = public_api.get(f'/api/django/crm/salle-vente/{token}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['items']), 3)
        body_str = str(resp.data)
        self.assertNotIn('prix_achat', body_str)

    def test_public_endpoint_expire_correctement(self):
        data = self._create_salle()
        token = data['token']
        salle = SalleVente.objects.get(token=token)
        salle.expires_at = timezone.now() - timezone.timedelta(days=1)
        salle.save(update_fields=['expires_at'])

        public_api = APIClient()
        resp = public_api.get(f'/api/django/crm/salle-vente/{token}/')
        self.assertEqual(resp.status_code, 410)

    def test_public_endpoint_404_jeton_inconnu(self):
        public_api = APIClient()
        resp = public_api.get('/api/django/crm/salle-vente/jeton-invalide/')
        self.assertEqual(resp.status_code, 404)
